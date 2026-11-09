import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

const hooksRules =
  reactHooks.configs.flat?.recommended?.rules ??
  reactHooks.configs.recommended?.rules ??
  reactHooks.configs['recommended-latest']?.rules ??
  {};

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'dev-dist/**', 'coverage/**'],
  },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      ...hooksRules,
      // React-compiler-grade pedantic rules: warn only — existing
      // fetch-on-mount and TDZ-in-effect patterns are runtime-correct.
      'react-hooks/immutability': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/purity': 'warn',
      'react-hooks/refs': 'warn',
      'no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      'no-undef': 'error',
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    files: [
      'src/**/*.test.{js,jsx}',
      'src/test/**/*.{js,jsx}',
      'src/setup.{js,jsx}',
    ],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
];
