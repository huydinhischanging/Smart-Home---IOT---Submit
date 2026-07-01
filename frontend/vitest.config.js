import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        url: 'http://localhost:5173',
      },
    },
    setupFiles: ['./test/setup.js'],
    include: [
      'test/alert.api.test.js',
      'test/auth.storage.test.js',
      'test/device.api.test.js',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        'test/',
        '**/*.config.js',
        '**/dist/**',
      ],
      lines: 70,
      functions: 70,
      branches: 70,
      statements: 70,
    },
  },
})
