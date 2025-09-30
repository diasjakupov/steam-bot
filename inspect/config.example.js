module.exports = {
  // Provide one or more Steam bot accounts used by CSFloat Inspect.
  logins: [
    {
      accountName: "steam_bot_username",
      password: "steam_bot_password",
      sharedSecret: "optional_shared_secret",
      identitySecret: "optional_identity_secret"
    }
  ],
  api: {
    port: 5000,
    host: "0.0.0.0"
  },
  database: {
    enabled: false,
    connectionString: "postgresql://user:pass@host:5432/csgofloat"
  }
};
