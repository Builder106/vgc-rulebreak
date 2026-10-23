import astro from 'eslint-plugin-astro';
import tseslint from 'typescript-eslint';

const deprecated = {
  plugins: { '@typescript-eslint': tseslint.plugin },
  rules: { '@typescript-eslint/no-deprecated': 'error' },
};

export default [
  ...astro.configs.recommended,
  {
    files: ['src/**/*.ts', 'tests/**/*.{js,mjs,ts}', '*.mjs'],
    ...deprecated,
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: { projectService: true },
    },
  },
  {
    files: ['src/**/*.astro'],
    ...deprecated,
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        project: './tsconfig.json',
        extraFileExtensions: ['.astro'],
      },
    },
  },
];
