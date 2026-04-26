import pino from 'pino';

export const logger = pino({
  browser: { asObject: true },
  level: import.meta.env.DEV ? 'debug' : 'info',
  base: { app: 'edict-dashboard' },
});
