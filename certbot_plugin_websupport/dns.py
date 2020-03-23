"""DNS Authenticator for Websupport."""
import logging

import requests
import zope.interface
import hmac
import hashlib
import base64
import time
from datetime import datetime

from certbot import errors
from certbot import interfaces
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)

API_ENDPOINT = 'https://rest.websupport.sk'
ACCOUNT_URL = 'https://admin.websupport.sk/sk/auth/apiKey'

@zope.interface.implementer(interfaces.IAuthenticator)
@zope.interface.provider(interfaces.IPluginFactory)
class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for Websupport

    This Authenticator uses the Websupport API to fulfill a dns-01 challenge.
    """

    description = ('Obtain certificates using a DNS TXT record (if you are using Websupport for '
                   'DNS).')
    ttl = 120

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credentials = None

    @classmethod
    def add_parser_arguments(cls, add):  # pylint: disable=arguments-differ
        super(Authenticator, cls).add_parser_arguments(add)
        add('credentials', help='Websupport credentials INI file.')

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return 'This plugin configures a DNS TXT record to respond to a dns-01 challenge using ' + \
               'the Websupport API.'

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            'credentials',
            'Websupport credentials INI file',
            {
                'api-key': 'API key for Websupport account, obtained from {0}'.format(ACCOUNT_URL),
                'api-secret': 'API secret for Websupport account, obtained from {0}'.format(ACCOUNT_URL)
            }
        )

    def _perform(self, domain, validation_name, validation):
        self._get_websupport_client().add_txt_record(domain, validation_name, validation, self.ttl)

    def _cleanup(self, domain, validation_name, validation):
        self._get_websupport_client().del_txt_record(domain, validation_name, validation)

    def _get_websupport_client(self):
        return _WebsupportClient(self.credentials.conf('api-key'), self.credentials.conf('api-secret'))


class _WebsupportClient(object):
    """
    Encapsulates all communication with the Websupport REST API.
    """

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret


    def add_txt_record(self, domain, record_name, record_content, record_ttl):
        """
        Add a TXT record using the supplied information.

        :param str domain: The domain to use to look up the Websupport zone.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :param int record_ttl: The record TTL (number of seconds that the record may be cached).
        :raises certbot.errors.PluginError: if an error occurs communicating with the Websupport API
        """

        zone_id = self._find_zone_id(domain)
        name = record_name.replace(zone_id, '').strip('.')

        data = {
            'type': 'TXT',
            'name': name,
            'content': record_content,
            'ttl': record_ttl
        }

        logger.debug('Attempting to add record to zone %s: %s', zone_id, data)
        response = self._send_request('POST', '/v1/user/self/zone/{0}/record'.format(zone_id), data)

        if response.status_code != 200 and response.status_code != 201:
            raise errors.PluginError('Error communicating with Websupport API: {0}'.format(response.status_code))

        response_json = response.json()
        if response_json['status'] == 'error':
            raise errors.PluginError('Error communicating with Websupport API: {0} - {1}'.format(response['errors']['name'][0], response['errors']['content'][0]))

        record_id = response_json['item']['id']
        logger.debug('Successfully added TXT record with record_id: %s', record_id)


    def del_txt_record(self, domain, record_name, record_content):
        """
        Delete a TXT record using the supplied information.

        Note that both the record's name and content are used to ensure that similar records
        created concurrently (e.g., due to concurrent invocations of this plugin) are not deleted.

        Failures are logged, but not raised.

        :param str domain: The domain to use to look up the Websupport zone.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        """

        try:
            zone_id = self._find_zone_id(domain)
        except errors.PluginError as e:
            logger.debug('Encountered error finding zone_id during deletion: %s', e)
            return

        name = record_name.replace(zone_id, '').strip('.')
        if zone_id:
            record_id = self._find_txt_record_id(zone_id, name, record_content)
            if record_id:
                response = self._send_request('DELETE', '/v1/user/self/zone/{0}/record/{1}'.format(zone_id, record_id))
                if response.status_code == 200:
                    logger.debug('Successfully deleted TXT record.')
                else:
                    logger.warning('Encountered Websupport error when deleting record: {0}'.format(record_id))
            else:
                logger.debug('TXT record not found; no cleanup needed.')
        else:
            logger.debug('Zone not found; no cleanup needed.')


    def _find_zone_id(self, domain):
        """
        Find the zone_id for a given domain.

        :param str domain: The domain for which to find the zone_id.
        :returns: The zone_id, if found.
        :rtype: str
        :raises certbot.errors.PluginError: if no zone_id is found.
        """

        parts = domain.split('.')
        zone_id = '.'.join(parts[-2:])

        response = self._send_request('GET', '/v1/user/self/zone/{0}'.format(zone_id))

        if response.status_code == 200:
            return zone_id
        elif response.status_code == 401 or response.status_code == 403:
            raise errors.PluginError('Error determining zone_id: {0} {1}. Please confirm that '
                                        'you have supplied valid Websupport API credentials.'
                                        .format(code, e))
        else:
            raise errors.PluginError('Unable to determine zone_id for {0}. '
                                    'Please confirm that the domain name has been entered correctly '
                                    'and is already associated with the supplied Websupport account.'
                                    .format(domain))

    def _find_txt_record_id(self, zone_id, record_name, record_content):
        """
        Find the record_id for a TXT record with the given name and content.

        :param str zone_id: The zone_id which contains the record.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :returns: The record_id, if found.
        :rtype: str
        """

        response = self._send_request('GET', '/v1/user/self/zone/{0}/record'.format(zone_id))

        if response.status_code == 404:
            logger.debug('Unable to find TXT record.')
            return None

        response_json = response.json()
        for item in response_json['items']:
            if item['type'] == 'TXT' and item['name'] == record_name and item['content'] == record_content:
                return item['id']
        else:
            logger.debug('Unable to find TXT record.')
            return None


    def _send_request(self, method, path, data=None):
        timestamp = int(time.time())
        canonical_request = "%s %s %s" % (method, path, timestamp)
        signature = hmac.new(self.api_secret, canonical_request.encode('utf-8'), hashlib.sha1).hexdigest()

        headers = {
            "Authorization": "Basic %s" % (base64.b64encode("%s:%s" % (self.api_key, signature))),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Date": datetime.fromtimestamp(timestamp).isoformat()
        }

        return requests.request(method, '%s%s' % (API_ENDPOINT, path), headers=headers, json=data)

