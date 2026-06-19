import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import PrimeVue from "primevue/config";
import ToastService from "primevue/toastservice";
import Tooltip from "primevue/tooltip";
import Button from "primevue/button";
import InputText from "primevue/inputtext";
import Calendar from "primevue/calendar";
import Dropdown from "primevue/dropdown";
import Message from "primevue/message";
import ProgressSpinner from "primevue/progressspinner";
import Toast from "primevue/toast";
import { library } from "@fortawesome/fontawesome-svg-core";
import { faHeart as faHeartRegular } from "@fortawesome/free-regular-svg-icons";
import { faHeart as faHeartSolid } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import App from "./App.vue";
import BaseJn from "../views/BaseJn.vue";
import jnRoutes from "../routes";
import FRAIHeader from "./glue/FRAIHeader.vue";
import FRAIDataTableExtended from "./glue/FRAIDataTableExtended.vue";
import "primeicons/primeicons.css";
import "./styles.css";

library.add(faHeartRegular, faHeartSolid);

const username = new URLSearchParams(window.location.search).get("username") ?? "Guest";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      component: BaseJn,
      meta: { username },
      children: jnRoutes,
    },
  ],
});

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.use(PrimeVue);
app.use(ToastService);
app.directive("tooltip", Tooltip);

app.component("Button", Button);
app.component("InputText", InputText);
app.component("Calendar", Calendar);
app.component("Dropdown", Dropdown);
app.component("Message", Message);
app.component("ProgressSpinner", ProgressSpinner);
app.component("Toast", Toast);
app.component("FRAIHeader", FRAIHeader);
app.component("FRAIDataTableExtended", FRAIDataTableExtended);
app.component("font-awesome-icon", FontAwesomeIcon);

app.mount("#app");
