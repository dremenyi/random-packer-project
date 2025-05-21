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

    def trenddsmsetup(self, adsecretspath, dsmsecretspath, region, domain, basedn, endpointurl):
        client = boto3.client('ssm', region_name=region,
                              endpoint_url=endpointurl)

        # Get default trenddsm admin password
        admin_password = client.get_parameter(
            Name=dsmsecretspath + 'masteradmin', WithDecryption=True)['Parameter']['Value']

        # Get trenddsm LDAP service account password
        svc_trenddsm_password = client.get_parameter(
            Name=adsecretspath + 'svc_trenddsm', WithDecryption=True)['Parameter']['Value']

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

        # Navigate to Administration Users page
        # Note: We're navigating directly to the URL to avoid dealing with a pop-up window
        logging.info(
            'Navigating Directly to Synchronize with Directory wizard')
        self.get("/SSOWizard.screen?")

        # Check for existing LDAP radio button and that it is selected
        if self.check_resync():
            if self.driver.find_element(By.ID, "oldSettings").is_selected():
                logging.info(
                    'Existing ldap configuration found, exiting Selenium script.')
                self.logoff_session()
                sys.exit()
            else:
                logging.info(
                    'Existing ldap configuration not found, continuing...')
        else:
            logging.info(
                'Existing ldap configuration not found, continuing...')

        # Fill in LDAP information
        logging.info('Filling in server address')
        self.driver.find_element(
            By.ID, "serverAddrexx").send_keys('dc1.' + domain)
        # logging.info('Filling in LDAP port')
        # self.driver.find_element(By.ID, "serverPort").send_keys("636")
        logging.info('Selecting "Username/Password LDAPS" from dropdown')
        access_dropdown = self.driver.find_element(By.ID, "accessMethod")
        access_dropdown.find_element(
            By.XPATH, "//option[. = 'Username/Password LDAPS']").click()
        logging.info('Filling in LDAP username')
        self.driver.find_element(By.ID, "serverAcct").send_keys(
            "svc_trenddsm@" + domain)
        logging.info('Filling in LDAP password')
        self.driver.find_element(By.ID, "serverPass").send_keys(
            svc_trenddsm_password)
        logging.info('Clicking on "Finish" button')
        self.driver.find_element(By.ID, "finish").click()

        # Wait for next page
        WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.ID, "searchFilter")))

        # Add Trend Admins AD group
        logging.info('Filling in "trendadmins" to search')
        self.driver.find_element(By.ID, "searchFilter").click()
        self.driver.find_element(
            By.ID, "searchFilter").send_keys("trendadmins")
        logging.info('Pressing "Enter" key')
        self.driver.find_element(By.ID, "searchFilter").send_keys(Keys.ENTER)
        logging.info('Locating "TrendAdmins" and clicking on item')
        # groups_dropdown = self.driver.find_element(By.ID, "filteredGroupSelector")
        self.driver.find_element(
            By.XPATH, "//option[. = 'TrendAdmins']").click()
        logging.info('Clicking ">>" button')
        self.driver.find_element(By.ID, "addGroupButton").click()
        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "finish").click()

        # Wait for next page
        WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.ID, "administratorRoleID")))

        # Assign TrendAdmins to Full Access
        logging.info('Clicking "Role" dropdown')
        self.driver.find_element(By.ID, "administratorRoleID").click()
        logging.info('Selecting "Full Access" from dropdown')
        # access_dropdown = self.driver.find_element(By.ID, "administratorRoleID")
        self.driver.find_element(
            By.XPATH, "//option[. = 'Full Access']").click()
        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "finish").click()
        WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.ID, "finish")))
        logging.info('Clicking "Finish" button')
        self.driver.find_element(By.ID, "finish").click()

        # Setting Synchronization Schedule
        window_before = self.driver.window_handles[0]
        self.vars["window_handles"] = self.driver.window_handles
        logging.info('Clicking "Close" button')
        self.driver.find_element(By.ID, "close").click()
        logging.info('Waiting for new window to load')
        self.vars["win7837"] = self.wait_for_window(2000)
        self.driver.switch_to.window(self.vars["win7837"])
        logging.info('Clicking "Hourly" radio button')
        self.driver.find_element(By.ID, "freq1").click()
        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "finish").click()
        WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.ID, "finish")))
        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "finish").click()
        WebDriverWait(self.driver, 30).until(
            EC.visibility_of_element_located((By.ID, "finish")))
        logging.info('Clicking "Finish" button')
        self.driver.find_element(By.ID, "finish").click()

        # Switch back to main window
        self.driver.switch_to.window(window_before)

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

    def check_resync(self):
        try:
            logging.info('Check for resynchronize radio button.')
            self.driver.find_element(By.ID, "oldSettings")
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
    driver.trenddsmsetup(args.adsecretspath, args.dsmsecretspath,
                         args.region, args.domain, args.basedn, args.endpointurl)

    driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--adsecretspath', required=True)
    parser.add_argument('--dsmsecretspath', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--basedn', required=True)
    parser.add_argument('--endpointurl', required=True)
    main(parser.parse_args())
