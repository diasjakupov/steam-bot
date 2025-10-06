# Inspect Service

This directory contains a thin wrapper around the [csfloat/inspect](https://github.com/csfloat/inspect) project. The worker and API call this service instead of the public CSFloat endpoint.

## Usage

```
npm install
npm start
```

The start script loads configuration from `config.js`, which in turn reads environment variables (either from the process or the repository-level `.env` file). When running under Docker Compose the service is available at `http://inspect:5000`.

## Configuration Cheatsheet

Set at least one Steam account to let the service authenticate against Valve:

- `STEAM_BOT_USER`
- `STEAM_BOT_PASS`
- `STEAM_BOT_AUTH` (optional 2FA shared secret or bootstrap code)

For multiple accounts either repeat the trio with the `INSPECT_BOT_*` prefix or provide a delimited list:

- `INSPECT_LOGINS=user1:pass1:auth1;user2:pass2`
- `INSPECT_LOGINS_JSON=[{"user":"name","pass":"secret","auth":"optional"}]`

Other useful knobs:

- `INSPECT_HTTP_PORT` (default `5000`)
- `INSPECT_MAX_ATTEMPTS` (retry count per item)
- `INSPECT_REQUEST_DELAY_MS` (delay between GC requests per bot)
- `INSPECT_REQUEST_TTL_MS` (timeout when calling Valve)
- `INSPECT_RATE_LIMIT_ENABLE`, `INSPECT_RATE_LIMIT_MAX`, `INSPECT_RATE_LIMIT_WINDOW_MS`
- `INSPECT_STEAM_USER_OPTIONS_JSON` to forward raw [node-steam-user](https://github.com/DoctorMcKay/node-steam-user#options-) options

See `config.js` for the complete list. Values are sanitized automatically, so unset variables fall back to sane defaults.

## Docker

`inspect/Dockerfile` builds a minimal image (Node 20 Alpine) and runs the bundled start script. The Compose setup in the repository root references this build context and forwards the repository-level `.env` file so you can manage all credentials in one place.
