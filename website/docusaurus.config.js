// @ts-check
/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Sqube Agent Control',
  tagline: 'Open-source infrastructure for controlling AI agent actions',
  url: 'https://sqube-groups.github.io',
  baseUrl: '/sqube-agent-control/',
  organizationName: 'Sqube-Groups',
  projectName: 'sqube-agent-control',
  trailingSlash: false,
  headTags: [
    {
      tagName: 'link',
      attributes: {
        rel: 'canonical',
        href: 'https://sqube-groups.github.io/sqube-agent-control/docs/intro',
      },
    },
  ],
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/Sqube-Groups/sqube-agent-control/tree/main/website/',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: 'Sqube Agent Control',
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docsSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://github.com/Sqube-Groups/sqube-agent-control',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        copyright: `Copyright © ${new Date().getFullYear()} Sqube Groups — Apache-2.0`,
      },
    }),
};

export default config;
