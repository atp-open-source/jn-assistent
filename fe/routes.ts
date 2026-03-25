import { RouteRecordRaw } from "vue-router";
import JNNotatView from "./views/JNNotatView.vue";
import JNConfigView from "./views/JNConfigView.vue";
import JNNotatOverblikView from "./views/JNNotatOverblikView.vue";

const jnRoutes: RouteRecordRaw[] = [
  {
    path: "",
    name: "JNnotatForslag",
    component: JNNotatView,
  },
  {
    path: "config",
    name: "JNconfig",
    component: JNConfigView,
  },
  {
    path: "notat_overblik",
    name: "JNnotatOverblik",
    component: JNNotatOverblikView,
  },
];

export default jnRoutes;
