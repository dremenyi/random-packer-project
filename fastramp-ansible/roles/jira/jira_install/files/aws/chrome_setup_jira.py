import logging
import argparse
import boto3
import distro
import sys
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
TIMEOUT = 30


class SetupJira:
    def __init__(self, base_url):
        if distro.id() == "ubuntu":
            # Note: For Ubuntu in particular, Chrome uses its own certificate store so it won't trust the custom CA even if the system does
            options = webdriver.ChromeOptions()
            options.add_argument("--ignore-ssl-errors=yes")
            options.add_argument("--ignore-certificate-errors")
        else:
            options = None
        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()), options=options
        )
        self.driver.maximize_window()
        self.driver.accept_untrusted_certs = True
        self.driver.implicitly_wait(TIMEOUT)
        self._base_url = base_url

    def get(self, relative_url):
        full_url = self._base_url + relative_url
        logging.info("Loading url: %s", full_url)
        self.driver.get(full_url)

    def jirasetup(
        self, jirasecretspath, dbhostname, email, region, endpointurl, domain, clustered
    ):
        client = boto3.client("ssm", region_name=region, endpoint_url=endpointurl)

        # Get default Jira admin password
        admin_password = client.get_parameter(
            Name=jirasecretspath + "admin", WithDecryption=True
        )["Parameter"]["Value"]

        # Get jira db password
        jira_db_password = client.get_parameter(
            Name=jirasecretspath + "db_password", WithDecryption=True
        )["Parameter"]["Value"]

        # Get jira license key
        jira_license = client.get_parameter(
            Name=jirasecretspath + "jira_license", WithDecryption=True
        )["Parameter"]["Value"]

        # Jira Setup page
        logging.info("Navigating to SetupMode")
        self.get("/secure/SetupMode!default.jspa")

        # Debugging
        get_url = self.driver.current_url
        logging.info("Current URL is " + get_url)

        # Check existing setup
        if self.check_for_existing_setup():
            logging.info("Existing setup found, exiting Selenium script.")
            sys.exit()
        else:
            logging.info("Existing setup not found, continuing...")

        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "img[src='/images/setup/setup-mode-advanced.png']")
            )
        )

        logging.info("Selecting \"I'll set it up myself")
        self.driver.find_element(
            By.CSS_SELECTOR, "img[src='/images/setup/setup-mode-advanced.png']"
        ).click()
        logging.info('Clicking "Next"')
        self.driver.find_element(By.ID, "jira-setup-mode-submit").click()

        # Setup database
        logging.info('Selecting "My Own Database" radio button')
        self.driver.find_element(
            By.CSS_SELECTOR, "label[for='jira-setup-database-field-database-external']"
        ).click()

        logging.info('Selecting "PostgresSQL" in "Database Type" dropdown')
        self.driver.find_element(
            By.ID, "jira-setup-database-field-database-type-field"
        ).click()
        self.driver.find_element(By.LINK_TEXT, "PostgreSQL").click()

        logging.info("Filling in database hostname")
        self.driver.find_element(By.ID, "jira-setup-database-field-hostname").send_keys(
            dbhostname
        )

        logging.info("Filling in database name")
        self.driver.find_element(
            By.ID, "jira-setup-database-field-database-name"
        ).send_keys("jira")

        logging.info("Filling in database username")
        self.driver.find_element(By.ID, "jira-setup-database-field-username").send_keys(
            "jira"
        )

        logging.info("Filling in database password")
        self.driver.find_element(By.ID, "jira-setup-database-field-password").send_keys(
            jira_db_password
        )

        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "jira-setup-database-submit").click()

        WebDriverWait(self.driver, 720).until(
            EC.presence_of_element_located((By.ID, "jira-setupwizard-submit"))
        )

        # Set up application properties
        logging.info("Filling in BaseURL")
        self.driver.find_element(By.NAME, "baseURL").clear()
        if clustered == "true":
            self.driver.find_element(By.NAME, "baseURL").send_keys(
                "https://jira." + domain + ":8443"
            )
        else:
            self.driver.find_element(By.NAME, "baseURL").send_keys(
                "https://jira1." + domain + ":8443"
            )

        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "jira-setupwizard-submit").click()

        WebDriverWait(self.driver, 180).until(
            EC.presence_of_element_located((By.ID, "licenseKey"))
        )

        # Specify your license key
        logging.info("Filling in license key")
        self.driver.find_element(By.ID, "licenseKey").send_keys(jira_license)

        logging.info('Clicking "Next" button')
        self.driver.find_element(By.CSS_SELECTOR, "input[value='Next']").click()

        WebDriverWait(self.driver, 180).until(
            EC.presence_of_element_located((By.NAME, "fullname"))
        )

        # Set up administrator account
        logging.info("Filling in fullname")
        self.driver.find_element(By.NAME, "fullname").send_keys("Admin")

        logging.info("Filling in administrator email")
        self.driver.find_element(By.NAME, "email").send_keys(email)

        logging.info("Filling in administrator username")
        self.driver.find_element(By.NAME, "username").send_keys("admin")

        logging.info("Filling in administrator password")
        self.driver.find_element(By.NAME, "password").send_keys(admin_password)
        self.driver.find_element(By.NAME, "confirm").send_keys(admin_password)

        logging.info('Clicking "Next" button')
        self.driver.find_element(By.ID, "jira-setupwizard-submit").click()

        # Set up email notifications
        # Default is Configure Email Notifications = Later
        logging.info('Clicking "Finish" button')
        self.driver.find_element(By.ID, "jira-setupwizard-submit").click()

        WebDriverWait(self.driver, 720).until(
            EC.presence_of_element_located((By.ID, "next"))
        )

        # Welcome to Jira; Language Selection page
        # Default is "English"
        logging.info('Clicking "Continue" button')
        self.driver.find_element(By.ID, "next").click()

        # Avatar selection page
        logging.info('Clicking "Choose an avatar" button')
        self.driver.find_element(
            By.XPATH, "//button[contains(text(), 'Choose an avatar')]"
        ).click()

        logging.info("Clicking the first avatar on the list")
        WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.ID, "avatar-10334"))
        ).click()

        logging.info('Clicking "Next" button')
        WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[value='Next']"))
        ).click()

        logging.info("Selenium Jira script completed!")

    def check_for_existing_setup(self):
        try:
            self.driver.find_element(
                By.XPATH, "//h1[contains(text(), 'Jira setup has already completed')]"
            )
        except NoSuchElementException:
            return False
        return True

    def quit(self):
        logging.info("Exiting SetupJira driver")
        self.driver.quit()


def main(args):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
    )
    logging.info("Starting script")
    driver = SetupJira(args.url)
    driver.jirasetup(
        args.jirasecretspath,
        args.dbhostname,
        args.email,
        args.region,
        args.endpointurl,
        args.domain,
        args.clustered,
    )

    driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--jirasecretspath", required=True)
    parser.add_argument("--dbhostname", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--endpointurl", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--clustered", required=True)
    main(parser.parse_args())
