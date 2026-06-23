declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

import "vue-router";

declare module "vue-router" {
  interface RouteMeta {
    username?: string;
  }
}

export {};
