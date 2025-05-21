import logging
import argparse
import boto3
import distro
import sys
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# Standard timeout (in seconds) to wait for a page element to appear.
TIMEOUT = 10


class SetupJira():
    def __init__(self, base_url):
        if distro.id() == 'ubuntu':
            # Note: For Ubuntu in particular, Chrome uses its own certificate store so it won't trust the custom CA even if the system does
            options = webdriver.ChromeOptions()
            options.add_argument('--ignore-ssl-errors=yes')
            options.add_argument('--ignore-certificate-errors')
        else:
            options = None
        self.driver = webdriver.Chrome(service=ChromeService(
            ChromeDriverManager().install()), options=options)
        self.driver.maximize_window()
        self.driver.accept_untrusted_certs = True
        self.driver.implicitly_wait(TIMEOUT)
        self._base_url = base_url

    def get(self, relative_url):
        full_url = self._base_url + relative_url
        logging.info('Loading url: %s', full_url)
        self.driver.get(full_url)

    def jirasetup(self, adsecretspath, jirasecretspath, region, endpointurl):
        client = boto3.client('ssm', region_name=region,
                              endpoint_url=endpointurl)

        # Get default Jira admin password
        admin_password = client.get_parameter(
            Name=jirasecretspath + 'admin', WithDecryption=True)['Parameter']['Value']

        # Jira Setup page
        logging.info('Navigating to Dashboard')
        self.get("/secure/Dashboard.jspa")

        # Login to Dashboard
        logging.info('Filling in administrator username')
        self.driver.find_element(
            By.ID, "login-form-username").send_keys("admin")

        logging.info('Filling in administrator password')
        self.driver.find_element(
            By.ID, "login-form-password").send_keys(admin_password)

        logging.info('Clicking "Submit" button')
        self.driver.find_element(By.ID, "login").click()

        # Wait after login for all pop-ups to load
        # Arbitrary wait is being used because one pop-up will obstruct another and I'm hoping the order is consistent
        # This arbitrary wait also seems important for a successful initial login (ChromeDriver)
        time.sleep(15)

        # Check for and close pop-ups if found
        self.close_generic_popup()
        self.close_generic_popup()
        self.close_insight_popup()

        # Checks Application Access page for 3rd element (JiraUsers)
        # If 3rd element found, assumes it is already configured and exits the script
        if self.check_for_application_access(admin_password):
            logging.info(
                'Existing application access found, exiting Selenium script.')
            sys.exit()
        else:
            logging.info(
                'Existing application access not found, continuing...')

        ### Set Global Permissions for JiraAdmins ###
        # Navigate to Application access page
        self.get("/secure/admin/GlobalPermissions!default.jspa")

        # Check for and authenticate to admin login page if prompted
        self.admin_login(admin_password)

        # Wait for page load
        try:
            WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.ID, 'globalPermType_select')))
        except TimeoutException:
            # Reload URL and try again
            self.get("/secure/admin/GlobalPermissions!default.jspa")
            WebDriverWait(self.driver, 20).until(
                EC.visibility_of_element_located((By.ID, 'globalPermType_select')))

        # Selecting Permission and Group
        # Add JiraAdmins to Jira System Administrators
        logging.info(
            'Selecting "Jira System Administrators from Permissions dropdown')
        permissions = self.driver.find_element(By.ID, 'globalPermType_select')
        self.driver.execute_script(
            "arguments[0].scrollIntoView();", permissions)
        ActionChains(self.driver).move_to_element(permissions).perform()
        permissions_select = Select(
            self.driver.find_element(By.ID, 'globalPermType_select'))
        permissions_select.select_by_visible_text('Jira System Administrators')

        logging.info('Scrolling to group input element')
        group = self.driver.find_element(
            By.ID, 'groupName_select-field')  # Input
        self.driver.execute_script("arguments[0].scrollIntoView();", group)
        ActionChains(self.driver).move_to_element(group).perform()
        group.click()
        self.driver.find_element(
            By.CSS_SELECTOR, "li[id^='jiraadmins'] > a > div > span").click()

        logging.info('Clicking "Add"')
        self.driver.find_element(By.ID, "addpermission_submit").click()

        logging.info('Waiting 5 seconds to process...')
        time.sleep(5)

        # Add JiraAdmins to Jira Administrators
        logging.info(
            'Selecting "Jira Administrators from Permissions dropdown')
        permissions = self.driver.find_element(By.ID, 'globalPermType_select')
        self.driver.execute_script(
            "arguments[0].scrollIntoView();", permissions)
        ActionChains(self.driver).move_to_element(permissions).perform()
        permissions_select = Select(
            self.driver.find_element(By.ID, 'globalPermType_select'))
        permissions_select.select_by_visible_text('Jira Administrators')

        logging.info('Scrolling to group input element')
        group = self.driver.find_element(
            By.ID, 'groupName_select-field')  # Input
        self.driver.execute_script("arguments[0].scrollIntoView();", group)
        ActionChains(self.driver).move_to_element(group).perform()
        group.click()
        self.driver.find_element(
            By.CSS_SELECTOR, "li[id^='jiraadmins'] > a > div > span").click()

        logging.info('Clicking "Add"')
        self.driver.find_element(
            By.CSS_SELECTOR, "#addpermission_submit").click()

        logging.info('Waiting 5 seconds to process...')
        time.sleep(5)

        logging.info('Selenium Jira script completed!')

    def check_for_admin_login(self):
        try:
            self.driver.find_element(By.ID, "login-form-authenticatePassword")
        except NoSuchElementException:
            return False
        return True

    def admin_login(self, admin_password):
        if self.check_for_admin_login():
            logging.info('Filling in administrator password')
            self.driver.find_element(
                By.ID, "login-form-authenticatePassword").send_keys(admin_password)

            logging.info('Clicking "Confirm" button')
            self.driver.find_element(By.ID, "login-form-submit").click()
        else:
            logging.info('Admin login page not found, continuing...')

    def check_for_application_access(self, admin_password):
        try:
            self.get("/secure/admin/ApplicationAccess.jspa")

            # Check for and authenticate to admin login page if prompted
            self.admin_login(admin_password)
            self.driver.find_element(
                By.XPATH, "//span[contains(text(), 'JiraAdmins')]")
        except NoSuchElementException:
            return False
        return True

    def check_for_generic_popup(self):
        try:
            self.driver.find_element(
                By.LINK_TEXT, "Don\'t remind me again")
        except NoSuchElementException:
            return False
        return True

    def close_generic_popup(self):
        if self.check_for_generic_popup():
            logging.info('Clicking "Don\'t remind me again" button on Generic pop-up.')
            generic_popup = self.driver.find_element(
                By.LINK_TEXT, "Don\'t remind me again")
            # Use Javascript to click as it won't be obstructed
            self.driver.execute_script(
                "arguments[0].click();", generic_popup)
        else:
            logging.info(
                'Prompt for Generic pop-up not found, skipping.')

    def check_for_insight_popup(self):
        try:
            self.driver.find_element(
                By.XPATH, "//button[@data-testid='onboarding-dismiss']/span[contains(text(), 'OK')]")
        except NoSuchElementException:
            return False
        return True

    def close_insight_popup(self):
        if self.check_for_insight_popup():
            logging.info('Clicking "OK" button on Check For Insight pop-up.')
            check_for_insight_popup = self.driver.find_element(
                By.XPATH, "//button[@data-testid='onboarding-dismiss']/span[contains(text(), 'OK')]")
            # Use Javascript to click as it won't be obstructed
            self.driver.execute_script(
                "arguments[0].click();", check_for_insight_popup)
        else:
            logging.info(
                'Onboarding prompt for Check For Insight pop-up not found, skipping.')

    def logoff_session(self):
        logging.info('Navigating to Dashboard')
        self.get("/secure/Dashboard.jspa")
        logging.info('Clicking current user')
        current_user = self.driver.find_element(
            By.CLASS_NAME, "aui-avatar-inner")
        # Use Javascript to click as it won't be obstructed
        self.driver.execute_script("arguments[0].click();", current_user)
        logging.info('Navigating to "Sign Out"')
        signout_url = self.driver.find_element(
            By.ID, "log_out").get_attribute("href")
        self.driver.get(signout_url)

    def quit(self):
        logging.info('Exiting SetupJira driver')
        self.driver.quit()


def main(args):
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    logging.info('Starting script')
    driver = SetupJira(args.url)
    driver.jirasetup(args.adsecretspath, args.jirasecretspath,
                     args.region, args.endpointurl)

    driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--adsecretspath', required=True)
    parser.add_argument('--jirasecretspath', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--endpointurl', required=True)
    main(parser.parse_args())
