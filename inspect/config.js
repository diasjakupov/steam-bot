const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');

const repoEnv = path.resolve(__dirname, '..', '.env');
if (fs.existsSync(repoEnv)) {
    dotenv.config({ path: repoEnv });
}

const localEnv = path.resolve(__dirname, '.env');
if (fs.existsSync(localEnv)) {
    dotenv.config({ path: localEnv, override: true });
}

function parseBoolean(value, fallback) {
    if (value === undefined || value === null || value === '') {
        return fallback;
    }
    const normalized = String(value).trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) {
        return true;
    }
    if (["0", "false", "no", "n", "off"].includes(normalized)) {
        return false;
    }
    return fallback;
}

function parseInteger(value, fallback) {
    if (value === undefined || value === null || value === '') {
        return fallback;
    }
    const parsed = Number.parseInt(String(value), 10);
    return Number.isNaN(parsed) ? fallback : parsed;
}

function parseList(value, separator = ',') {
    if (!value) {
        return [];
    }
    return String(value)
        .split(separator)
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0);
}

function sanitizeLogin(login) {
    return Object.fromEntries(
        Object.entries(login).filter(([_, value]) => value !== undefined && value !== null && String(value).length > 0),
    );
}

function parseLogins() {
    const logins = [];

    const json = process.env.INSPECT_LOGINS_JSON;
    if (json) {
        try {
            const parsed = JSON.parse(json);
            if (Array.isArray(parsed)) {
                for (const login of parsed) {
                    if (login && login.user && login.pass) {
                        logins.push(sanitizeLogin(login));
                    }
                }
            }
        } catch (error) {
            console.warn('inspect.config.invalid_logins_json', error);
        }
    }

    if (logins.length === 0) {
        const delimited = process.env.INSPECT_LOGINS;
        if (delimited) {
            for (const chunk of delimited.split(';')) {
                const [user, pass, auth] = chunk.split(':').map((part) => part && part.trim());
                if (user && pass) {
                    logins.push(sanitizeLogin({ user, pass, auth }));
                }
            }
        }
    }

    if (logins.length === 0) {
        const user = process.env.INSPECT_BOT_USER || process.env.STEAM_BOT_USER;
        const pass = process.env.INSPECT_BOT_PASS || process.env.STEAM_BOT_PASS;
        const auth = process.env.INSPECT_BOT_AUTH || process.env.STEAM_BOT_AUTH;
        if (user && pass) {
            logins.push(sanitizeLogin({ user, pass, auth }));
        }
    }

    if (logins.length === 0) {
        throw new Error('No inspect bot logins configured. Set INSPECT_LOGINS_JSON, INSPECT_LOGINS, or STEAM_BOT_* variables.');
    }

    return logins;
}

function parseSteamUserOptions() {
    const raw = process.env.INSPECT_STEAM_USER_OPTIONS_JSON;
    if (!raw) {
        return {};
    }
    try {
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (error) {
        console.warn('inspect.config.invalid_steam_user_options', error);
    }
    return {};
}

const httpPort = parseInteger(process.env.INSPECT_HTTP_PORT, 80);

module.exports = {
    // Configuration for the HTTP API server
    'http': {
        'port': httpPort,
    },
    // Whether to trust a forwarding proxy's IP (trust X-Forwarded-For)
    'trust_proxy': parseBoolean(process.env.INSPECT_TRUST_PROXY, false),
    // List of usernames and passwords for the Steam accounts
    'logins': parseLogins(),
    // Optional HTTP/SOCKS5 proxies to auto-rotate for each bot in a round-robin
    'proxies': parseList(process.env.INSPECT_PROXIES),
    // Bot settings
    'bot_settings': {
        // Amount of attempts for each request to Valve
        'max_attempts': parseInteger(process.env.INSPECT_MAX_ATTEMPTS, 1),
        // Amount of milliseconds to wait between subsequent requests to Valve (per bot)
        'request_delay': parseInteger(process.env.INSPECT_REQUEST_DELAY_MS, 1100),
        // Amount of milliseconds to wait until a request to Valve is timed out
        'request_ttl': parseInteger(process.env.INSPECT_REQUEST_TTL_MS, 2000),
        // OPTIONAL: Settings for Steam User (https://github.com/DoctorMcKay/node-steam-user#options-)
        'steam_user': parseSteamUserOptions(),
    },
    // Origins allowed to connect to the HTTP/HTTPS API
    'allowed_origins': parseList(process.env.INSPECT_ALLOWED_ORIGINS).concat([
        'http://steamcommunity.com',
        'https://steamcommunity.com',
    ]),
    // Origins allowed to connect to the HTTP/HTTPS API with Regex
    'allowed_regex_origins': parseList(process.env.INSPECT_ALLOWED_REGEX_ORIGINS).length
        ? parseList(process.env.INSPECT_ALLOWED_REGEX_ORIGINS)
        : ['https://.*\\.steamcommunity\\.com'],
    // Optionally configure a global rate limit across all endpoints
    'rate_limit': {
        'enable': parseBoolean(process.env.INSPECT_RATE_LIMIT_ENABLE, false),
        'window_ms': parseInteger(process.env.INSPECT_RATE_LIMIT_WINDOW_MS, 60 * 60 * 1000),
        'max': parseInteger(process.env.INSPECT_RATE_LIMIT_MAX, 10000),
    },
    // Logging Level (error, warn, info, verbose, debug, silly)
    'logLevel': process.env.INSPECT_LOG_LEVEL || 'debug',
    // Max amount of simultaneous requests from the same IP  (incl. WS and HTTP/HTTPS), -1 for unlimited
    'max_simultaneous_requests': parseInteger(process.env.INSPECT_MAX_SIMULTANEOUS_REQUESTS, 1),
    // Bool to enable game file updates from the SteamDB Github tracker (updated item definitions, images, names)
    'enable_game_file_updates': parseBoolean(process.env.INSPECT_ENABLE_GAME_FILE_UPDATES, true),
    // Amount of seconds to wait between updating game files (0 = No Interval Updates)
    'game_files_update_interval': parseInteger(process.env.INSPECT_GAME_FILES_UPDATE_INTERVAL, 3600),
    // Postgres connection string to store results in
    'database_url': process.env.INSPECT_DATABASE_URL || '',
    // OPTIONAL: Enable bulk inserts, may improve performance with many requests
    'enable_bulk_inserts': parseBoolean(process.env.INSPECT_ENABLE_BULK_INSERTS, false),
    // OPTIONAL: Key by the caller to allow inserting price information, required to use the feature
    'price_key': process.env.INSPECT_PRICE_KEY || '',
    // OPTIONAL: Key by the caller to allow placing bulk searches
    'bulk_key': process.env.INSPECT_BULK_KEY || '',
    // OPTIONAL: Maximum queue size allowed before dropping requests
    'max_queue_size': parseInteger(process.env.INSPECT_MAX_QUEUE_SIZE, -1),
};
