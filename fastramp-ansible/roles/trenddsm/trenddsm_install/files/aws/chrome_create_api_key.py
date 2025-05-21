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


class Setuptrenddsm():
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
        self.driver.implicitly_wait(TIMEOUT)
        self._base_url = base_url
        self.vars = {}

    def get(self, relative_url):
        full_url = self._base_url + relative_url
        logging.info('Loading url: %s', full_url)
        self.driver.get(full_url)

    def wait_for_window(self, timeout=2):
        time.sleep(round(timeout / 1000))
        wh_now = self.driver.window_handles
        wh_then = self.vars["window_handles"]
        if len(wh_now) > len(wh_then):
            return set(wh_now).difference(set(wh_then)).pop()

    def trenddsmsetup(self, adsecretspath, dsmsecretspath, region, domain, basedn, kmskeyid, endpointurl):
        client = boto3.client('ssm', region_name=region,
                              endpoint_url=endpointurl)

        # Get default trenddsm admin password
        admin_password = client.get_parameter(
            Name=dsmsecretspath + 'masteradmin', WithDecryption=True)['Parameter']['Value']

        # trenddsm Sign-in page
        logging.info('Navigating to Sign-in Screen')
        self.get("/SignIn.screen")

        # Login to Dashboard
        logging.info('Filling in administrator username')
        self.driver.find_element(By.ID, "username").send_keys("masteradmin")

        logging.info('Filling in administrator password')
        self.driver.find_element(By.ID, "password").send_keys(admin_password)

        # Check for Terms and Conditions checkbox and click it if it exists
        if self.check_terms():
            logging.info('Terms and Conditions checkbox found, clicking.')
            terms_checkbox = self.driver.find_element(
                By.ID, "termsAndConditionsCheckBox")
            # Using Javascript click because a "fake checkbox" label obscures the actual checkbox
            self.driver.execute_script("arguments[0].click();", terms_checkbox)
        else:
            logging.info(
                'Terms and Conditions checkbox not found, continuing...')

        logging.info('Clicking "Sign In" button')
        self.driver.find_element(By.ID, "signinButton").click()

        # Navigate to Administration > User Management > API Keys
        logging.info('Navigating to API Keys URL')
        self.get("/APIKeys.screen?")

        # Check for Existing API Key
        if self.check_api_key():
            logging.info('Existing api key found, exiting Selenium script.')
            self.logoff_session()
            sys.exit()
        else:
            logging.info('Existing api key not found, continuing...')

        # Navigate to Administration Users page
        logging.info('Navigating directly to API Key Wizard')
        self.get("/APIKeyWizard.screen")

        # Fill in API Key information
        logging.info('Filling in API Key Name')
        self.driver.find_element(By.ID, "name").send_keys("DSM API Key")
        logging.info('Selecting "Full Access" from dropdown')
        self.driver.find_element(By.ID, "administratorRoleID").click()
        dropdown = self.driver.find_element(By.ID, "administratorRoleID")
        dropdown.find_element(By.XPATH, "//option[. = 'Full Access']").click()
        logging.info('Clicking "Next>"')
        self.driver.find_element(By.ID, "finish").click()

        # Wait for next page
        WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.ID, "apiKey")))

        # Write secret to SSM Parameter Store
        logging.info('Saving API Key to SSM Parameter Store')
        api_key = self.driver.find_element(By.ID, "apiKey").text
        response = client.put_parameter(
            Name=dsmsecretspath + 'dsm_api_key',
            KeyId=kmskeyid,
            Type='SecureString',
            Overwrite=True,
            Value=api_key
        )

        logging.info('Clicking "Close" button')
        self.driver.find_element(By.ID, "closeButton").click()

        self.logoff_session()

        logging.info('Selenium trenddsm script completed!')

    def logoff_session(self):
        # Navigate back to Dashboard and sign-out
        # Note: The sessions do not time out quickly, this signs out otherwise you can't login if there are too many sessions open
        logging.info('Navigating to Dashboard')
        self.get("/")
        logging.info('Clicking "masteradmin" user')
        self.driver.find_element(By.ID, "signedInUsername").click()
        logging.info('Clicking "Sign Out"')
        self.driver.find_element(
            By.CSS_SELECTOR, "#dsm-signout-link > a").click()

    def check_api_key(self):
        try:
            logging.info('Check for existing "DSM API Key"')
            self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'DSM API Key')]")
        except NoSuchElementException:
            return False
        return True

    def check_terms(self):
        try:
            logging.info('Check for Terms and Conditions checkbox.')
            self.driver.find_element(By.ID, "termsAndConditionsCheckBox")
        except NoSuchElementException:
            return False
        return True

    def quit(self):
        logging.info('Exiting Setuptrenddsm driver')
        self.driver.quit()


def main(args):
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    logging.info('Starting script')
    driver = Setuptrenddsm(args.url)
    driver.trenddsmsetup(args.adsecretspath, args.dsmsecretspath, args.region,
                         args.domain, args.basedn, args.kmskeyid, args.endpointurl)

    driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--adsecretspath', required=True)
    parser.add_argument('--dsmsecretspath', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--basedn', required=True)
    parser.add_argument('--kmskeyid', required=True)
    parser.add_argument('--endpointurl', required=True)
    main(parser.parse_args())
