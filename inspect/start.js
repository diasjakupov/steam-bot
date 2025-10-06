const path = require('path');

// Ensure the csgofloat entrypoint sees an explicit --config argument.
const hasConfigFlag = process.argv.some((arg, index, argv) => {
  if (arg === '--config') {
    return true;
  }
  if (arg.startsWith('--config=')) {
    return true;
  }
  if (arg.startsWith('-c') && arg !== '-c') {
    // Support short flag joined to value (e.g. -c=foo)
    return true;
  }
  if (arg === '-c') {
    return true;
  }
  return false;
});

if (!hasConfigFlag) {
  const configPath = path.resolve(__dirname, 'config.js');
  process.argv.push('--config', configPath);
}

require('./node_modules/csgofloat/index.js');
