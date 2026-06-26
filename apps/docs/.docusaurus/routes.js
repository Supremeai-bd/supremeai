import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/docs',
    component: ComponentCreator('/docs', 'd49'),
    routes: [
      {
        path: '/docs',
        component: ComponentCreator('/docs', 'bb4'),
        routes: [
          {
            path: '/docs',
            component: ComponentCreator('/docs', '1da'),
            routes: [
              {
                path: '/docs/api-reference',
                component: ComponentCreator('/docs/api-reference', '67f'),
                exact: true
              },
              {
                path: '/docs/bangla-guide',
                component: ComponentCreator('/docs/bangla-guide', 'e71'),
                exact: true
              },
              {
                path: '/docs/intro',
                component: ComponentCreator('/docs/intro', '61d'),
                exact: true,
                sidebar: "tutorialSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
