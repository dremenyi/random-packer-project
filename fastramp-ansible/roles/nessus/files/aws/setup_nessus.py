import logging
import argparse
import boto3
import sys
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
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

class SetupNessus():
  def __init__(self, base_url):
    self.driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()))
    # Because of how Firefox certificates work, the RootCA will likely be untrusted
    # even if the Linux system trusts it.
    self.driver.accept_untrusted_certs = True
    self.driver.implicitly_wait(TIMEOUT)
    self._base_url = base_url

  def get(self, relative_url):
    full_url = self._base_url + relative_url
    logging.info('Loading url: %s', full_url)
    self.driver.get(full_url)
  
  
  def nessussetup(self, nessussecretspath, region, ssmendpointurl, secretsendpointurl):
    ssm_client = boto3.client('ssm', region_name=region, endpoint_url=ssmendpointurl)
    secrets_client = boto3.client('secretsmanager', region_name=region, endpoint_url=secretsendpointurl)

    # Get default Nessus admin password
    admin_password = secrets_client.get_secret_value(SecretId=nessussecretspath + 'nessus')['SecretString']

    # Get nessus license key
    nessus_license = ssm_client.get_parameter(Name=nessussecretspath + 'nessus_license', WithDecryption=True)['Parameter']['Value']

    # Nessus Setup page
    logging.info('Navigating to Setup Page')
    self.get("/")

    # Check login screen
    if self.check_for_login():
      logging.info('Existing login screen found, exiting Selenium script.')
      sys.exit(0)
    else:
      logging.info('Existing login screen not found, continuing...')

    logging.info('Waiting for "Continue" button')
    WebDriverWait(self.driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "button[data-name='continue']")))

    logging.info('Clicking "Continue" button')
    self.driver.find_element(By.CSS_SELECTOR, "button[data-name='continue']").click()

    logging.info('Clicking "Continue" button again')
    self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='btn-continue-activation-method']").click()

    logging.info('Clicking "Skip" button')
    self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='btn-skip-login']").click()
    
    logging.info('Filling in Nessus license key')
    self.driver.find_element(By.CSS_SELECTOR, "input[aria-label='Activation Code']").send_keys(nessus_license)
    logging.info('Clicking "Continue" button')
    self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='btn-continue-register']").click()
    logging.info('Clicking "Continue" button again')
    self.driver.find_element(By.CSS_SELECTOR, "button[data-name='continue']").click()

    logging.info('Filling in username')
    self.driver.find_element(By.CSS_SELECTOR, "input[data-field='username']").send_keys("nessus")
    logging.info('Filling in password')
    self.driver.find_element(By.CSS_SELECTOR, "input[data-field='password']").send_keys(admin_password)
    logging.info('Clicking "Submit" button')
    self.driver.find_element(By.CSS_SELECTOR, "button[data-name='submit']").click()

    logging.info('Waiting for "Settings" link')
    WebDriverWait(self.driver, 900).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a[data-topnav-menu='settings']")))

    logging.info('Selenium Nessus script completed!')

  def check_for_login(self):
    try:
        self.driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']")
    except NoSuchElementException:
        return False
    return True

  def quit(self):
    logging.info('Exiting SetupNessus driver')
    self.driver.quit()

def main(args):
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    logging.info('Starting script')
    driver = SetupNessus(args.url)
    driver.nessussetup(args.nessussecretspath, args.region, args.ssmendpointurl, args.secretsendpointurl)

    driver.quit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--nessussecretspath', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--ssmendpointurl', required=True)
    parser.add_argument('--secretsendpointurl', required=True)
    main(parser.parse_args())