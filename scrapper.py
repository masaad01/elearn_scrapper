import os
import platform
import shutil
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirfoxService
from webdriver_manager.firefox import GeckoDriverManager

import sqlalchemy as db
from database_connection import DatabaseConnection
from users import User
import hashlib


_elearn_URL = r"https://learn.ejust.org/first23/my/"


def geckodriver_path():
    os_m = platform.system()
    if os_m.find("Linux") != -1:
        if shutil.which("geckodriver") is None:
            print("geckodriver not found. Installing...")
            os.system("sudo add-apt-repository ppa:ubuntu-mozilla-security/ppa ")
            os.system("sudo apt install firefox-geckodriver")
        return "geckodriver"
    else:
        return GeckoDriverManager().install()


def myhash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LoginError(Exception):
    def __init__(self, *args, **kwargs):
        self.message = args[0] if args else None
        Exception.__init__(self, *args, **kwargs)


class ElearnScrapper:
    valid_types = ["course", "section", "messages", "activity", None]
    geckodriver_path = geckodriver_path()
    def __init__(self, user: User):
        self.set_user(user)
        self.browser = None
        self.is_logged_in = False
        self._courses_urls = None

    def set_user(self, user: User):
        if type(user) is not User:
            raise TypeError("user must be of type User")
        valid_users = User.get_all_users()
        if user not in valid_users:
            raise ValueError("user not found")
        self._user = user

    def _open_browser(self, headless=True):
        service = FirfoxService(executable_path=self.geckodriver_path)
        options = webdriver.FirefoxOptions()
        options.headless = headless


        browser = webdriver.Firefox(service=service, options=options)
        browser.implicitly_wait(2)
        browser.set_window_position(0, 0)
        browser.set_window_size(360, 740)


        self.browser = browser

    def _close_browser(self):
        if self.browser is not None:
            self.browser.close()
            self.browser = None

    def _login(self):
        if self.browser is None:
            self._open_browser()

        try:
            self.browser.get(_elearn_URL)
            self.browser.find_element(
                By.XPATH, r"//a[normalize-space()='Microsoft']").click()
            sleep(1)
            self.browser.find_element(
                By.XPATH, r"//input[contains(@placeholder,'Email or phone')]").send_keys(self._user.get_email())
            self.browser.find_element(
                By.XPATH, r"//input[@value='Next']").click()
            sleep(1)
            self.browser.find_element(
                By.XPATH, r"//input[contains(@placeholder,'Password')]").send_keys(self._user.get_password())
            self.browser.find_element(
                By.XPATH, r"//input[@value='Sign in']").click()
            sleep(1)
            self.browser.find_element(
                By.XPATH, r"//input[@value='No']").click()
            sleep(3)
        except Exception as e:
            print(e)
            self._close_browser()
            self.is_logged_in = False
            if self.browser.find_elements(By.XPATH, r"//input[@value='Sign in']"):
                raise LoginError("Invalid credentials")
            elif self.browser.find_elements(By.XPATH, r"//input[@value='Next']"):
                raise LoginError("Your organization needs more info to sign you in")
            else:
                raise LoginError("Unknown error")
        else:
            self.is_logged_in = True

    def _get_courses_urls(self, force=False):
        if self._courses_urls is not None and not force:
            return self._courses_urls
        if not self.is_logged_in:
            self._login()
        elif self.browser.current_url != _elearn_URL:
            self.browser.get(_elearn_URL)
        courses_cards = self.browser.find_elements(
            By.XPATH, r"//div[contains(@data-region,'paged-content-page')]//a")

        courses_urls = []
        for card in courses_cards:
            url = card.get_attribute("href")
            if url.find("course/view.php") != -1 and url not in courses_urls:
                courses_urls.append(url)

        self._courses_urls = courses_urls
        return courses_urls

    def get_course_data(self, course_url):
        if not self.is_logged_in:
            self._login()

        try:
            urls = self._get_courses_urls()
            if course_url not in urls:
                urls = self._get_courses_urls(force=True)
                if course_url not in urls:
                    raise Exception("Invalid course URL.")
            self.browser.get(course_url)
        except Exception as e:
            print(e)
            return None
        sleep(1)
        content = self.browser.find_element(
            By.XPATH, r"//div[@id='page-content']")

        if not self._is_course_changed(course_url, content.text):
            return None

        course_data = {}
        course_data["course_name"] = self.browser.find_element(
            By.XPATH, r"//header[@id='page-header']").text
        course_data["course_url"] = course_url
        course_data["course_sections"] = []

        sections = content.find_elements(
            By.XPATH, r"//ul[contains(@class,'topics') or contains(@class,'weeks')]//li[contains(@id,'section')]")

        for section in sections:
            section_data = {}
            section_data["section_name"] = section.find_element(
                By.XPATH, r".//div[contains(@class,'course-section-header')]//h3").text

            if not self._is_section_changed(course_url, section_data["section_name"], section.text):
                continue

            section_data["activities"] = []
            activities_elements = section.find_elements(
                By.XPATH, r".//li[contains(@class,'activity')]")

            if len(activities_elements) == 0:
                continue

            for elem in activities_elements:
                try:
                    elem.find_element(By.XPATH, r".//button[contains(@title,'is marked as done')]")
                except Exception as e:
                    pass
                else:
                    continue

                if not self._is_activity_changed(course_url, section_data["section_name"], elem.text):
                    continue

                activity_data = {}
                activity_data["text"] = elem.text
                activity_data["links"] = []
                links = elem.find_elements(By.XPATH, r".//a")
                for link in links:
                    activity_data["links"].append(link.get_attribute("href"))

                activity_data["screen_shot_path"] = f"./tmp/{myhash(activity_data['text'] + section.text + content.text)}.png"
                elem.screenshot(activity_data['screen_shot_path'])
                section_data["activities"].append(activity_data)

            course_data["course_sections"].append(section_data)

        return course_data

    def get_all_courses_data(self):
        courses_urls = self._get_courses_urls()
        courses_data = []
        number_of_courses = len(courses_urls)
        for i, url in enumerate(courses_urls):
            course_data = self.get_course_data(url)
            if course_data is not None:
                courses_data.append(course_data)
            print(f"Course {i+1}/{number_of_courses} done.")
        self._close_browser()
        return courses_data

    def _is_course_changed(self, course_url, course_text):
        course_hash = myhash(course_text)
        item_id = myhash(course_url)
        if self.set_hash(item_id, course_hash, "course"):
            return True
        return False

    def _is_section_changed(self, course_url, section_name, section_text):
        section_hash = myhash(section_text)
        item_id = myhash(course_url + section_name)
        if self.set_hash(item_id, section_hash, "section"):
            return True
        return False

    def _is_activity_changed(self, course_url, section_name, activity_text):
        activity_hash = myhash(activity_text)
        item_id = myhash(course_url + section_name + activity_text)
        if self.set_hash(item_id, activity_hash, "activity"):
            return True
        return False

    def get_hash(self, item_id):
        with DatabaseConnection() as connection:

            table = connection.get_table("last_updated")
            query = db.select([table]).where(
                table.columns.id == item_id, table.columns.user_id == self._user.get_user_id())
            result_proxy = connection.execute(query)
            if result_proxy is None:
                return None
            row = result_proxy.fetchone()
            if row is None:
                return None
            return row["hash"]

    def set_hash(self, item_id, hash, type=None):
        if type not in self.valid_types:
            type = None
        with DatabaseConnection() as connection:
            old_hash = self.get_hash(item_id)
            if old_hash == hash:
                return False
            table = connection.get_table("last_updated")
            if old_hash is None:
                query = db.insert(table).values(
                    id=item_id, user_id=self._user.get_user_id(), hash=hash, type=type)
                connection.execute(query)
            else:
                query = db.update(table).where(table.columns.id == item_id,
                                               table.columns.user_id == self._user.get_user_id()).values(hash=hash)
                connection.execute(query)
            return True

    def __del__(self):
        self._close_browser()


if __name__ == "__main__":
    user = User.get_all_users()[0]
    scrapper = ElearnScrapper(user)
    courses_data = scrapper.get_all_courses_data()
    print(courses_data)