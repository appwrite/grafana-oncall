const { TestEnvironment } = require('jest-environment-jsdom');

// jsdom does not supply fetch; use the native Node implementations, without a polyfill.
module.exports = class extends TestEnvironment {
  async setup() {
    await super.setup();
    Object.assign(this.global, { fetch, Request, Response, Headers });
  }
};
