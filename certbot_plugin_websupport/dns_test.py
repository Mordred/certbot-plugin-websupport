import sys
sys.path.insert(0, '../')

import unittest

import mock

from certbot import errors
from certbot.compat import os
from certbot.plugins import dns_test_common
from certbot.plugins.dns_test_common import DOMAIN
from certbot.tests import util as test_util

FAKE_API_KEY = "api_key"
FAKE_API_SECRET = "secret"

class AuthenticatorTest(
    test_util.TempDirTestCase, dns_test_common.BaseAuthenticatorTest
):
    def setUp(self):
        super(AuthenticatorTest, self).setUp()

        mock.patch("certbot.display.util.notify", lambda x: ...).start()

        from certbot_plugin_websupport.dns import Authenticator

        path = os.path.join(self.tempdir, "websupport.ini")
        dns_test_common.write(
            {
                "websupport_api_key": FAKE_API_KEY,
                "websupport_api_secret": FAKE_API_SECRET,
            },
            path,
        )

        super(AuthenticatorTest, self).setUp()
        self.config = mock.MagicMock(
            websupport_credentials=path, websupport_propagation_seconds=0
        )  # don't wait during tests

        self.auth = Authenticator(self.config, "websupport")

        self.mock_client = mock.MagicMock()
        # _get_ispconfig_client | pylint: disable=protected-access
        self.auth._get_websupport_client = mock.MagicMock(return_value=self.mock_client)

    def test_perform(self):
        self.auth.perform([self.achall])

        expected = [
            mock.call.add_txt_record(
                DOMAIN, "_acme-challenge." + DOMAIN, mock.ANY, mock.ANY
            )
        ]
        self.assertEqual(expected, self.mock_client.mock_calls)

    def test_cleanup(self):
        # _attempt_cleanup | pylint: disable=protected-access
        self.auth._attempt_cleanup = True
        self.auth.cleanup([self.achall])

        expected = [
            mock.call.del_txt_record(
                DOMAIN, "_acme-challenge." + DOMAIN, mock.ANY
            )
        ]
        self.assertEqual(expected, self.mock_client.mock_calls)


# class WebsupportClient(unittest.TestCase):

#     def test_wrong_credentials_for_find_zone_id(self):
#         client = _WebsupportClient('api_key', 'secret')
#         with self.assertRaises(errors.PluginError):
#             client._find_zone_id('mydomain.cz')


if __name__ == '__main__':
    unittest.main()
