module.exports = {
  // Populate this array with at least one Steam account configuration.
  // See inspect/config.example.js for the expected shape.
  accounts: [],
  api: {
    port: 5000,
    host: "0.0.0.0"
  },
  database: {
    enabled: false,
    connectionString: "postgresql://user:pass@host:5432/csgofloat"
  }
};
