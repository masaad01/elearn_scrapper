import json
import os
import platform
import shutil
from random import randrange
from time import sleep

from bs4 import BeautifulSoup
from pydoc_data.topics import topics
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirfoxService
from webdriver_manager.firefox import GeckoDriverManager

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


class Scrapper:
    def __init__(self, email="", passwd=""):
        self.email = email
        self.password = passwd
        self.browser = None
        self.is_logged_in = False
        # {course_url: {course_hash, "course_sections": {"section_name": section_hash,...}}}
        with open("./course_hashes.json", "r") as f:
            self.course_hashes = json.load(f)

    def _open_browser(self, headless=True):
        service = FirfoxService(executable_path=geckodriver_path())
        options = webdriver.FirefoxOptions()
        options.headless = headless

        browser = webdriver.Firefox(service=service, options=options)
        browser.implicitly_wait(2)

        self.browser = browser

    def _close_browser(self):
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
                By.XPATH, r"//input[contains(@placeholder,'Email or phone')]").send_keys(self.email)
            self.browser.find_element(
                By.XPATH, r"//input[@value='Next']").click()
            sleep(1)
            self.browser.find_element(
                By.XPATH, r"//input[contains(@placeholder,'Password')]").send_keys(self.password)
            self.browser.find_element(
                By.XPATH, r"//input[@value='Sign in']").click()
            sleep(1)
            self.browser.find_element(
                By.XPATH, r"//input[@value='No']").click()
            sleep(3)
        except Exception as e:
            print(e)
            self.is_logged_in = False
        else:
            self.is_logged_in = True

    def _get_courses_urls(self):
        if not self.is_logged_in:
            self._login()

        courses_cards = self.browser.find_elements(
            By.XPATH, r"//div[contains(@data-region,'paged-content-page')]//a")

        courses_urls = []
        for card in courses_cards:
            url = card.get_attribute("href")
            if url.find("course/view.php") != -1 and url not in courses_urls:
                courses_urls.append(url)

        for url in courses_urls:
            self.course_hashes[url] = {
                "course_sections": {}, "course_hash": None}
        return courses_urls

    def get_course_data(self, course_url):
        if not self.is_logged_in:
            self._login()

        try:
            if course_url not in self.course_hashes:
                self._get_courses_urls()
            if course_url not in self.course_hashes:
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
            for elem in activities_elements:
                activity_data = {}
                activity_data["text"] = elem.text
                activity_data["links"] = []
                links = elem.find_elements(By.XPATH, r".//a")
                for link in links:
                    activity_data["links"].append(link.get_attribute("href"))

                activity_data["screenshot"] = f"{abs(hash(activity_data['text'] + section.text + content.text))}.png"
                elem.screenshot(f"./tmp/{activity_data['screenshot']}")
                section_data["activities"].append(activity_data)

            course_data["course_sections"].append(section_data)

        return course_data

    def get_all_courses_data(self):
        courses_urls = self.course_hashes.keys()
        courses_data = []
        for url in courses_urls:
            courses_data.append(self.get_course_data(url))

        return courses_data

    def _is_course_changed(self, course_url, course_text):
        if course_url not in self.course_hashes:
            return False
        if self.course_hashes[course_url]["course_hash"] != hash(course_text):
            self.course_hashes[course_url]["course_hash"] = hash(course_text)
            with open("./course_hashes.json", "w") as f:
                json.dump(self.course_hashes, f)
            return True
        return False

    def _is_section_changed(self, course_url, section_name, section_text):
        if section_name not in self.course_hashes[course_url]["course_sections"]:
            self.course_hashes[course_url]["course_sections"][section_name] = hash(
                section_text)
            with open("./course_hashes.json", "w") as f:
                json.dump(self.course_hashes, f)
            return True
        if self.course_hashes[course_url]["course_sections"][section_name] != hash(section_text):
            self.course_hashes[course_url]["course_sections"][section_name] = hash(
                section_text)
            with open("./course_hashes.json", "w") as f:
                json.dump(self.course_hashes, f)
            return True
        return False
