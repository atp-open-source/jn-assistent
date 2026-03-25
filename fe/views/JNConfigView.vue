<!-- 
JNConfigView
________________________________________________________________________________________

Denne komponent indeholder konfigurationssiden, som bruges til at se, rette, slette 
eller tilføje konfigurationer kunderådgivere, som er brugere af Journalnotatsassistenten.
________________________________________________________________________________________

Funktionaliteter:
  - Søg på konfiguration for kunderådgiver
  - Indsæt eller opdatér konfiguration for kunderådgiver
  - Slet konfiguration for kunderådgiver
-->

<!------------------- HTML FOR SIDEN ------------------->

<template>
  <body id="jn">
    <div id="jn" class="container">
      <header>
        <h1>JN Konfiguration</h1>
      </header>
      <div class="description-wrapper">
        <p class="description">
          Her kan du rette eller indsætte en konfiguration for én eller flere
          kunderådgivere, som bruger Journalnotatsassistenten.
        </p>
        <p class="description">
          Derudover kan du også søge eller slette eksisterende konfigurationer
          for en enkelt kunderådgiver.
        </p>
      </div>

      <!-- De primære funktionalitetsknapper -->

      <div v-if="isAuthorized">
        <div class="action-buttons">
          <Button
            label="Søg konfiguration"
            icon="pi pi-search"
            class="p-button-primary"
            @click="
              showSearchForm = true;
              showInsertForm = false;
              showDeleteForm = false;
            "
            :outlined="!showSearchForm"
          />
          <Button
            label="Indsæt konfiguration"
            icon="pi pi-plus"
            class="p-button-primary"
            @click="
              showInsertForm = true;
              showSearchForm = false;
              showDeleteForm = false;
            "
            :outlined="!showInsertForm"
          />
          <Button
            label="Slet konfiguration"
            icon="pi pi-trash"
            class="p-button-primary"
            @click="
              showDeleteForm = true;
              showSearchForm = false;
              showInsertForm = false;
            "
            :outlined="!showDeleteForm"
          />
        </div>

        <!-- Hvis bruger har valgt at søge på konfiguration -->

        <div v-if="showSearchForm" class="config-section">
          <div class="input-container">
            <div class="input-field-wrapper">
              <span class="p-float-label">
                <InputText
                  id="initialer"
                  v-model="initialer"
                  class="w-full"
                  @keyup.enter="fetchKrConfig"
                />
                <label for="initialer">Kunderådgivers initialer</label>
              </span>
              <Button
                label="Hent konfiguration"
                icon="pi pi-search"
                class="search-button"
                @click="fetchKrConfig"
                :disabled="!initialer"
              />
            </div>
          </div>

          <div v-if="loading" class="spinner-container">
            <ProgressSpinner class="spinner" />
            <div class="spinner-text">Henter konfiguration...</div>
          </div>

          <div v-else-if="errorMessage" class="error-message">
            <Message severity="error" :closable="false">{{
              errorMessage
            }}</Message>
          </div>

          <div v-else-if="configData" class="config-data">
            <h3>Konfiguration for {{ initialer.toUpperCase() }}</h3>
            <div class="config-table">
              <div
                v-for="(value, key) in configData"
                :key="key"
                class="config-row"
              >
                <div class="config-key">{{ key }}</div>
                <div class="config-value">{{ value }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Hvis bruger har valgt at indsætte ny konfiguration -->

        <div v-if="showInsertForm" class="config-section">
          <div class="insert-form">
            <div class="form-field">
              <span class="p-float-label">
                <InputText
                  id="kr_initialer"
                  v-model="newConfig.kr_initialer"
                  class="w-full"
                  placeholder="f.eks. ABCD, EFGH, IJKL"
                />
                <label for="kr_initialer">
                  Kunderådgivers initialer*
                  <i
                    class="pi pi-users"
                    style="margin-left: 0.5rem; color: #666"
                  ></i>
                </label>
              </span>
              <small class="p-help">
                <i class="pi pi-info-circle" style="margin-right: 0.25rem"></i>
                Adskil flere initialer med komma (f.eks. ABCD, EFGH, IJKL)
              </small>
              <small v-if="v$.kr_initialer.$error" class="p-error">{{
                v$.kr_initialer.$errors[0].$message
              }}</small>
            </div>

            <div class="form-field">
              <span class="p-float-label">
                <Dropdown
                  id="miljoe"
                  v-model="newConfig.miljoe"
                  :options="miljoOptions"
                  optionLabel="name"
                  optionValue="value"
                  class="w-full"
                />
                <label for="miljoe">Miljø*</label>
              </span>
              <small v-if="v$.miljoe.$error" class="p-error">{{
                v$.miljoe.$errors[0].$message
              }}</small>
            </div>

            <div class="form-field">
              <span class="p-float-label">
                <Dropdown
                  id="streamer_version"
                  v-model="newConfig.streamer_version"
                  :options="versionAudiostreamerOptions"
                  optionLabel="name"
                  optionValue="value"
                  class="w-full"
                />
                <label for="streamer_version">Version af audiostreamer*</label>
              </span>
              <small v-if="v$.streamer_version.$error" class="p-error">{{
                v$.streamer_version.$errors[0].$message
              }}</small>
            </div>

            <div class="form-field">
              <span class="p-float-label">
                <Dropdown
                  id="transcriber_version"
                  v-model="newConfig.transcriber_version"
                  :options="versionTranscriberOptions"
                  optionLabel="name"
                  optionValue="value"
                  class="w-full"
                />
                <label for="transcriber_version">Version af transcriber*</label>
              </span>
              <small v-if="v$.transcriber_version.$error" class="p-error">{{
                v$.transcriber_version.$errors[0].$message
              }}</small>
            </div>

            <div class="form-field">
              <span class="p-float-label">
                <Dropdown
                  id="chatgpt_version"
                  v-model="newConfig.chatgpt_version"
                  :options="versionModelOptions"
                  optionLabel="name"
                  optionValue="value"
                  class="w-full"
                />
                <label for="chatgpt_version">Sprogmodel*</label>
              </span>
              <small v-if="v$.chatgpt_version.$error" class="p-error">{{
                v$.chatgpt_version.$errors[0].$message
              }}</small>
            </div>

            <div class="form-field">
              <span class="p-float-label">
                <InputText
                  id="forretningsomraade"
                  v-model="newConfig.forretningsomraade"
                  class="w-full"
                />
                <label for="forretningsomraade">Forretningsområde*</label>
              </span>
              <small v-if="v$.forretningsomraade.$error" class="p-error">{{
                v$.forretningsomraade.$errors[0].$message
              }}</small>
            </div>

            <div class="form-field">
              <span class="p-float-label">
                <Dropdown
                  id="controller_version"
                  v-model="newConfig.controller_version"
                  :options="controllerOptions"
                  optionLabel="name"
                  optionValue="value"
                  class="w-full"
                />
                <label for="controller_version">Version af controller*</label>
              </span>
              <small v-if="v$.controller_version.$error" class="p-error">{{
                v$.controller_version.$errors[0].$message
              }}</small>
            </div>

            <div class="form-buttons">
              <Button
                label="Indsæt konfiguration"
                icon="pi pi-save"
                @click="handleSaveConfig"
              />
              <Button
                label="Annullér"
                icon="pi pi-times"
                class="p-button-secondary"
                @click="resetForm"
                outlined
                :disabled="!hasAnyValue"
              />
            </div>
          </div>
        </div>

        <!-- Hvis bruger har valgt at slette en konfiguration -->

        <div v-if="showDeleteForm" class="config-section">
          <div class="input-container">
            <div class="input-field-wrapper">
              <span class="p-float-label">
                <InputText
                  id="deleteInitialer"
                  v-model="deleteInitialer"
                  class="w-full"
                  @keyup.enter="fetchConfigForDeletion"
                />
                <label for="deleteInitialer">Kunderådgivers initialer</label>
              </span>
              <Button
                label="Hent konfiguration"
                icon="pi pi-search"
                class="search-button"
                @click="fetchConfigForDeletion"
                :disabled="!deleteInitialer"
              />
            </div>
          </div>

          <div v-if="deleteLoading" class="spinner-container">
            <ProgressSpinner class="spinner" />
            <div class="spinner-text">Henter konfiguration...</div>
          </div>

          <div v-else-if="deleteErrorMessage" class="error-message">
            <Message severity="error" :closable="false">{{
              deleteErrorMessage
            }}</Message>
          </div>

          <div v-else-if="deleteConfigData" class="config-data">
            <h3>
              Er du sikker på at du vil slette konfiguration for
              {{ deleteConfigData.kr_initialer.toUpperCase() }}?
            </h3>
            <div class="config-table">
              <div
                v-for="(value, key) in deleteConfigData"
                :key="key"
                class="config-row"
              >
                <div class="config-key">{{ key }}</div>
                <div class="config-value">{{ value }}</div>
              </div>
            </div>

            <div class="form-buttons">
              <Button
                label="Slet konfiguration"
                icon="pi pi-trash"
                class="p-button-danger"
                @click="confirmDelete"
              />
              <Button
                label="Annullér"
                icon="pi pi-times"
                class="p-button-secondary"
                @click="cancelDelete"
                outlined
              />
            </div>
          </div>
        </div>
      </div>
      <Toast position="top-center" />
    </div>
  </body>
</template>

<!------------------- SCRIPT FOR SIDEN ------------------->

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useApiStore } from "../stores/JNapi.js";
import { useToast } from "primevue/usetoast";
import { useVuelidate } from "@vuelidate/core";
import { required, minLength, helpers } from "@vuelidate/validators";

const apiStore = useApiStore();
const toast = useToast();
const isAuthorized = ref(false);
const authorizedUsers = ["REDACTED"];

// Når siden mountes, tjekkes om brugeren har adgang
onMounted(async () => {
  const username = await apiStore.fetchUsername();
  if (username && authorizedUsers.includes(username)) {
    isAuthorized.value = true;
  } else {
    toast.add({
      severity: "error",
      summary: "Ikke autoriseret",
      detail: "Du har ikke adgang til at ændre i konfigurationerne for JN.",
      life: 8000,
    });
  }
});

const initialer = ref("");
const configData = ref<any>(null);
const loading = ref(false);
const errorMessage = ref("");
const showSearchForm = ref(false);
const showInsertForm = ref(false);
const showDeleteForm = ref(false);
const deleteInitialer = ref("");
const deleteConfigData = ref<any>(null);
const deleteLoading = ref(false);
const deleteErrorMessage = ref("");

// ---------------- Søg på konfiguration ---------------- //

const fetchKrConfig = async () => {
  /**
   * Henter konfiguration for initialer på kunderådgiver, som er givet som input.
   */
  if (!initialer.value.trim()) {
    errorMessage.value = "Indtast venligst kunderådgivers initialer";
    return;
  }

  loading.value = true;
  errorMessage.value = "";
  configData.value = null;

  try {
    const config = await apiStore.fetchConfig(initialer.value);

    if (config && config.kr_initialer) {
      configData.value = config;
    } else {
      errorMessage.value =
        "Ingen konfiguration fundet for de angivne initialer";
    }
  } catch (error) {
    console.error("Fejl ved hentning af konfiguration:", error);
    errorMessage.value = "Der opstod en fejl ved hentning af konfigurationen";
  } finally {
    loading.value = false;
  }
};

const handleSaveConfig = async () => {
  /**
   * Håndterer klik på "Indsæt konfiguration" knappen fortæller, hvis inputfelterne
   * ikke er udfyldt korrekt.
   */
  const isValid = await v$.value.$validate();

  // Hvis formularen ikke er korrekt, vises en fejlmeddelelse
  if (!isValid) {
    // Find de manglende felter
    const missingFields = Object.keys(v$.value).filter(
      (field) =>
        // @ts-ignore
        v$.value[field].$error,
    );

    // Opret en læsbar liste over manglende felter
    const fieldLabels: Record<string, string> = {
      kr_initialer: "Kunderådgivers initialer",
      miljoe: "Miljø",
      streamer_version: "Version af audiostreamer",
      transcriber_version: "Version af transcriber",
      chatgpt_version: "Sprogmodel",
      forretningsomraade: "Forretningsområde",
      controller_version: "Version af controller",
    };

    const missingFieldLabels = missingFields
      .map((field) => fieldLabels[field])
      .join(", ");

    // Vis fejlmeddelelse
    toast.add({
      severity: "error",
      summary: "Manglende felter",
      detail: `Udfyld venligst alle påkrævede felter: ${missingFieldLabels}`,
      life: 5000,
    });
    return;
  }

  // Hvis formularen er valid, gemmer vi konfigurationen
  await saveConfig();
};

const saveConfig = async () => {
  /**
   * Gemmer eller opdaterer konfiguration for kunderådgiver.
   */

  // Validerer formularen
  const result = await v$.value.$validate();
  if (!result) return;
  loading.value = true;

  // Opretter en ny konfiguration baseret på inputfelterne
  try {
    const response = await apiStore.insertConfig(
      newConfig.kr_initialer,
      newConfig.miljoe,
      newConfig.streamer_version,
      newConfig.transcriber_version,
      newConfig.chatgpt_version,
      newConfig.forretningsomraade,
      newConfig.controller_version,
    );

    // Vis succes toast hvis der er nogle der lykkedes
    if (response.successfulKr.length > 0) {
      toast.add({
        severity: "success",
        summary: "Konfiguration gemt",
        detail:
          response.successfulKr.length === 1
            ? `Konfiguration gemt for ${response.successfulKr[0]}`
            : `Konfiguration gemt for: ${response.successfulKr.join(", ")}`,
        life: 8000,
      });
    }

    // Vis fejl toast hvis der er nogle der fejlede
    if (response.failedKr.length > 0) {
      toast.add({
        severity: "error",
        summary: "Fejl ved gemning",
        detail:
          response.failedKr.length === 1
            ? `Fejl ved gemning af konfiguration for ${response.failedKr[0]}. \n\nRet fejlen og prøv igen.`
            : `Fejl ved gemning af konfiguration for: ${response.failedKr.join(", ")}. \n\nDe fejlede initialer er indsat i feltet - ret fejlen og prøv igen.`,
        life: 10000,
      });

      // Sæt de fejlede initialer tilbage i input-feltet, så brugeren nemt kan prøve igen
      newConfig.kr_initialer = response.failedKr.join(", ");
    }

    // Nulstil formularen kun hvis ALLE lykkedes
    if (response.failedKr.length === 0) {
      resetForm();

      // Hvis konfigurationen lige er blevet gemt, skal visningen opdateres
      if (
        initialer.value.toLowerCase() === newConfig.kr_initialer.toLowerCase()
      ) {
        fetchKrConfig();
      }
    }
  } catch (error) {
    console.error("Fejl ved indsættelse af konfiguration:", error);
    toast.add({
      severity: "error",
      summary: "Fejl",
      detail: "Der opstod en uventet fejl. Prøv igen senere.",
      life: 8000,
    });
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  /**
   * Nulstiller formularen newConfig samt valideringsfejl.
   */
  Object.keys(newConfig).forEach((key) => {
    // @ts-ignore
    newConfig[key] = "";
  });
  v$.value.$reset();
};

// ---------------- Tilføj konfiguration ---------------- //

// Placeholder konfiguration til at gemme data
const newConfig = reactive({
  kr_initialer: "",
  miljoe: "",
  streamer_version: "",
  transcriber_version: "",
  chatgpt_version: "",
  forretningsomraade: "",
  controller_version: "",
});

// Dropdown-muligheder for de forskellige felter
const miljoOptions = [
  { name: "Udvikling (dev)", value: "dev" },
  { name: "Produktion (prod)", value: "prod" },
];

const versionAudiostreamerOptions = [
  { name: "kafka", value: "kafka" },
  { name: "azure", value: "azure" },
  { name: "openai", value: "openai" },
];

const versionTranscriberOptions = [
  { name: "kafka", value: "kafka" },
  { name: "azure", value: "azure" },
];

const versionModelOptions = [
  { name: "kafka", value: "kafka" },
  { name: "azure", value: "azure" },
];

const controllerOptions = [
  { name: "On-Premise", value: "onprem" },
  { name: "Azure", value: "azure" },
];

// Valideringsregler for inputfelter
const rules = {
  kr_initialer: {
    required: helpers.withMessage("Initialer er påkrævet", required),
    minLength: helpers.withMessage(
      "Initialer skal være mindst 2 tegn",
      minLength(2),
    ),
  },
  miljoe: { required: helpers.withMessage("Miljø er påkrævet", required) },
  streamer_version: {
    required: helpers.withMessage("Streamerversion er påkrævet", required),
  },
  transcriber_version: {
    required: helpers.withMessage("Transcriberversion er påkrævet", required),
  },
  chatgpt_version: {
    required: helpers.withMessage("Sprogmodel er påkrævet", required),
  },
  forretningsomraade: {
    required: helpers.withMessage("Forretningsområde er påkrævet", required),
  },
  controller_version: {
    required: helpers.withMessage("Controller er påkrævet", required),
  },
};
const v$ = useVuelidate(rules, newConfig);

// Tjekker om der er nogen værdier i konfigurationen
const hasAnyValue = computed(() => {
  return Object.values(newConfig).some((value) => value !== "");
});

// ---------------- Slet konfiguration ---------------- //

const fetchConfigForDeletion = async () => {
  /**
   * Henter konfiguration for initialer på kunderådgiver, som er givet som input.
   */
  if (!deleteInitialer.value.trim()) {
    deleteErrorMessage.value = "Indtast venligst kunderådgivers initialer";
    return;
  }

  deleteLoading.value = true;
  deleteErrorMessage.value = "";
  deleteConfigData.value = null;

  try {
    // Brug fetchConfig men med de indtastede initialer
    const config = await apiStore.fetchConfig(deleteInitialer.value);

    if (config) {
      deleteConfigData.value = config;
    } else {
      deleteErrorMessage.value =
        "Ingen konfiguration fundet for de angivne initialer";
    }
  } catch (error) {
    console.error("Fejl ved hentning af konfiguration:", error);
    deleteErrorMessage.value =
      "Der opstod en fejl ved hentning af konfigurationen";
  } finally {
    deleteLoading.value = false;
  }
};

const confirmDelete = async () => {
  /**
   * Bekræft sletning af konfiguration for kunderådgiver.
   */
  deleteLoading.value = true;

  try {
    // Slet konfigurationen
    const response = await apiStore.deleteConfig(deleteInitialer.value);

    if (response.success) {
      toast.add({
        severity: "success",
        summary: `Konfigurationen for ${deleteInitialer.value.toUpperCase()} blev slettet`,
        life: 3000,
      });
      cancelDelete();

      // Hvis vi lige har slettet den samme konfiguration, som vi viste, skal vi nulstille visningen
      if (
        initialer.value.toLowerCase() === deleteInitialer.value.toLowerCase()
      ) {
        configData.value = null;
      }
    } else {
      toast.add({
        severity: "error",
        summary: "Fejl",
        life: 5000,
      });
    }
  } catch (error) {
    console.error("Fejl ved sletning af konfiguration:", error);
    toast.add({
      severity: "error",
      summary: "Fejl",
      detail: "Der opstod en uventet fejl ved sletning. Prøv igen senere.",
      life: 5000,
    });
  } finally {
    deleteLoading.value = false;
  }
};

const cancelDelete = () => {
  /**
   * Annuller sletning af konfiguration og nulstil inputfeltet.
   */
  deleteInitialer.value = "";
  deleteConfigData.value = null;
  deleteErrorMessage.value = "";
};
</script>

<style scoped>
.container {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}

header {
  margin-bottom: 2rem;
  text-align: center;
  padding-bottom: 1rem;
  border-bottom: 2px solid #e0e0e0;
}

h1 {
  color: var(--primary2-color);
  margin-bottom: 0.5rem;
}

h2 {
  color: var(--primary2-color);
  margin-bottom: 1rem;
  font-size: 1.5rem;
}

.description {
  color: #666;
  font-size: 1.1rem;
}

.description-wrapper {
  padding-bottom: 1.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid #e0e0e0;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.config-section {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.input-container {
  display: flex;
  justify-content: center;
  margin: 1rem;
}

.input-field-wrapper {
  display: flex;
  gap: 1rem;
  width: 100%;
  max-width: 500px;
}

.search-button {
  align-self: flex-start;
}

.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 0;
}

.spinner-text {
  margin-top: 1rem;
  color: var(--primary2-color);
}

.error-message {
  margin: 1rem 0;
  text-align: center;
}

.config-data {
  margin-top: 1rem;
}

.config-table {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.config-row {
  display: flex;
  padding: 0.75rem;
  background-color: white;
  border-radius: 4px;
  border-left: 3px solid var(--primary2-color);
}

.config-key {
  width: 40%;
  font-weight: bold;
  color: var(--primary2-color);
}

.config-value {
  width: 60%;
  word-break: break-word;
}

.insert-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 600px;
  margin: 0 auto;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-buttons {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}

.p-error {
  color: #f44336;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.unauthorized-message {
  margin: 1rem;
}
</style>
