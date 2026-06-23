import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/bn/docs',
    component: ComponentCreator('/bn/docs', '8e4'),
    routes: [
      {
        path: '/bn/docs',
        component: ComponentCreator('/bn/docs', 'b01'),
        routes: [
          {
            path: '/bn/docs',
            component: ComponentCreator('/bn/docs', '418'),
            routes: [
              {
                path: '/bn/docs/api-reference',
                component: ComponentCreator('/bn/docs/api-reference', '11f'),
                exact: true
              },
              {
                path: '/bn/docs/bangla-guide',
                component: ComponentCreator('/bn/docs/bangla-guide', '048'),
                exact: true
              },
              {
                path: '/bn/docs/intro',
                component: ComponentCreator('/bn/docs/intro', 'd80'),
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
