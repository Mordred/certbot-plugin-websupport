# Certbot plugin for authentication using Websupport REST API

This is a plugin for [Certbot](https://certbot.eff.org/) that uses the Websupport REST API to allow [Websupport](https://wwww.websupport.sk/)
customers to prove control of a domain name.

## Usage

1. Obtain an API key and API secret (see [Account Page](https://admin.websupport.sk/sk/auth/apiKey))

2. Install the plugin using `pip install certbot-plugin-websupport`

3. Create a `websupport.ini` config file with the following contents and apply `chmod 600 websupport.ini` on it:
   ```
   dns_websupport_api_key = APIKEY
   dns_websupport_api_secret = SECRET
   ```
   Replace `APIKEY` with your Websupport API key, `SECRET` with your API secret and ensure permissions are set
   to disallow access to other users.

4. Run `certbot` and direct it to use the plugin for authentication and to use
   the config file previously created:
   ```
   certbot certonly -a dns-websupport --dns-websupport-credentials websupport.ini -d domain.com
   ```
   Add additional options as required to specify an installation plugin etc.

Please note that this solution is usually not relevant if you're using Websupport's web hosting services as Websupport offers free automated certificates for all simplehosting plans having SSL in the admin interface.

## Updates

This plugin can be updated by running:

```
pip install certbot-plugin-websupport --upgrade
```

## Wildcard certificates

This plugin is particularly useful when you need to obtain a wildcard certificate using dns challenges:

```
certbot certonly -a dns-websupport --dns-websupport-credentials websupport.ini -d domain.com -d \*.domain.com
```

## Automatic renewal

You can setup automatic renewal using `crontab` with the following job for weekly renewal attempts:

```
0 0 * * 0 certbot renew -q -a dns-websupport --dns-websupport-credentials /etc/letsencrypt/websupport.ini
```
