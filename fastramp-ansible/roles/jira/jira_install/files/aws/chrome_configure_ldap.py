import logging
import argparse
import boto3
import distro
import sys
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException
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

    def jirasetup(self, adsecretspath, jirasecretspath, region, domain, basedn, endpointurl):
        client = boto3.client('ssm', region_name=region,
                              endpoint_url=endpointurl)

        # Get default Jira admin password
        admin_password = client.get_parameter(
            Name=jirasecretspath + 'admin', WithDecryption=True)['Parameter']['Value']

        # Get Jira LDAP service account password
        svc_jira_password = client.get_parameter(
            Name=adsecretspath + 'svc_jira', WithDecryption=True)['Parameter']['Value']

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

        # Navigate to LDAP page
        self.get("/secure/admin/user/UserBrowser.jspa")

        # Wait after login for all pop-ups to load
        # Arbitrary wait is being used because one pop-up will obstruct another and I'm hoping the order is consistent
        time.sleep(15)

        # Check for and close pop-ups if found
        self.close_generic_popup()
        self.close_insight_popup()

        logging.info('Filling in administrator password')
        self.driver.find_element(
            By.ID, "login-form-authenticatePassword").send_keys(admin_password)

        logging.info('Clicking "Confirm" button')
        self.driver.find_element(By.ID, "login-form-submit").click()

        # Configure LDAP
        logging.info('Clicking "User Directories"')
        self.driver.find_element(By.ID, "user_directories").click()

        # Check existing directory
        if self.check_for_directory():
            logging.info('Existing directory found, exiting Selenium script.')
            self.logoff_session()
            sys.exit()
        else:
            logging.info('Existing directory not found, continuing...')

        logging.info('Clicking "Add Directory"')
        self.driver.find_element(By.ID, "new-directory").click()

        # Default dropdown value is Microsoft AD
        logging.info('Clicking "Next"')
        self.driver.find_element(
            By.CSS_SELECTOR, "input[value='Next']").click()

        logging.info('Filling in "name" textbox')
        self.driver.find_element(
            By.ID, "configure-ldap-form-name").send_keys("DC1")

        logging.info('Filling in "hostname" textbox')
        self.driver.find_element(
            By.ID, "configure-ldap-form-hostname").send_keys('dc1.' + domain)

        logging.info('Click "Use SSL" checkbox')
        ssl_checkbox = self.driver.find_element(
            By.XPATH, "//div[@class='checkbox']/input[@id='configure-ldap-form-useSSL']")
        # Use Javascript to click as it won't be obstructed
        self.driver.execute_script("arguments[0].click();", ssl_checkbox)

        logging.info('Filling in "username" textbox')
        self.driver.find_element(
            By.ID, "configure-ldap-form-ldapUserdn").send_keys('svc_jira@' + domain)

        logging.info('Filling in "password" textbox')
        self.driver.find_element(
            By.ID, "configure-ldap-form-ldapPassword").send_keys(svc_jira_password)

        logging.info('Filling in "Base DN" textbox')
        self.driver.find_element(
            By.ID, "configure-ldap-form-ldapBasedn").send_keys(basedn)

        logging.info('Click "Read Only, with Local Groups" radio button')
        ldap_groups_radio_button = self.driver.find_element(
            By.XPATH, "//div[@class='radio']/input[@id='configure-ldap-form-ldapPermissionOption-READ_ONLY_LOCAL_GROUPS']")
        # Use Javascript to click as it won't be obstructed
        self.driver.execute_script(
            "arguments[0].click();", ldap_groups_radio_button)

        logging.info('Click "Save and Test" button')
        self.driver.find_element(By.ID, "configure-ldap-form-submit").click()

        self.logoff_session()

        logging.info('Selenium Jira script completed!')

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

    def check_for_directory(self):
        try:
            self.driver.find_element(
                By.XPATH, "//span[contains(text(), 'DC1')]")
        except NoSuchElementException:
            return False
        return True

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
                     args.region, args.domain, args.basedn, args.endpointurl)

    driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--adsecretspath', required=True)
    parser.add_argument('--jirasecretspath', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--basedn', required=True)
    parser.add_argument('--endpointurl', required=True)
    main(parser.parse_args())
