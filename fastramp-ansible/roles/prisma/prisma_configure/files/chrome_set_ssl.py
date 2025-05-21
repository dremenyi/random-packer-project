import logging
import argparse
import boto3
import distro
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
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


class SetupPrisma():
    def __init__(self, base_url):

        options = webdriver.ChromeOptions()
        options.add_argument('--ignore-ssl-errors=yes')
        options.add_argument('--ignore-certificate-errors')

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

    def prismasetup(self, prismasecretspath, region, endpointurl):
        client = boto3.client('ssm', region_name=region,
                              endpoint_url=endpointurl)

        # Get default prisma admin password
        prisma_cert = client.get_parameter(
            Name=casecretspath + 'prisma_cert', WithDecryption=True)['Parameter']['Value']

        prisma_cert_key = client.get_parameter(
            Name=casecretspath + 'prisma_cert_key', WithDecryption=True)['Parameter']['Value']

        # prisma Login page
        logging.info('Navigating to System certificates')
        self.get("/#!/manage/authentication/system-certificates")

        logging.info('Expanding "TLS certificate for Console"')
        self.driver.find_element(
            By.XPATH, "//div[contains(text(), 'TLS certificate for Console')]").click()

        # Check for LDAP auth (if present, already have a login user)
        logging.info("Check for LDAP auth")
        if self.check_existing_ssl():
            logging.info(
                'Existing ldap authentication option found, exiting Selenium script.')
            sys.exit()
        else:
            logging.info(
                'Existing ldap authentication option not found, continuing...')

        # Setup default admin
        logging.info('Filling in concatenated certificate')
        self.driver.find_element(
            By.CSS_SELECTOR, "textarea[placeholder='Upload the certificate in PEM format.']").send_keys(prisma_cert + '\\n' + prisma_cert_key)

        logging.info('Clicking "Save" button')
        self.driver.find_element(
            By.XPATH, "//span[contains(text(), 'Save')]").click()

        time.sleep(5)

        logging.info('Selenium prisma script completed!')

    def quit(self):
        logging.info('Exiting Setupprisma driver')
        self.driver.quit()


def check_existing_ssl(self):
    try:
        logging.info('Check for existing SSL certificate')
        self.driver.find_element(
            By.XPATH, "//span[contains(text(), 'Certificate is encrypted')]")
    except NoSuchElementException:
        return False
    return True


def main(args):
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    logging.info('Starting script')
    driver = SetupPrisma(args.url)
    driver.prismasetup(args.prismasecretspath,
                       args.region, args.endpointurl)

    driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--prismasecretspath', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--endpointurl', required=True)
    main(parser.parse_args())
