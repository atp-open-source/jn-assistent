<!--
JNNotatOverblik
________________________________________________________________________________________

Komponenten giver brugeren mulighed for at se notater og feedback til dem.
Der kan filtreres på dato og udsøgning i kolonnerne.
________________________________________________________________________________________

Funktionaliteter:
- Filtrer notater ud fra input 
- Hver notat vises med feedback og vurdering

Importerede komponenter:
- `JNDownloadOverblikComponent`: Komponent til at downloade eller kopiere notatoverblikket

DataStore funktioner:
- 'fetchNotatData' bruges til at hente notater fra API'et.
-->

<template>
  <body id="jn">
    <div class="p-4 container">
      <!-- Dato filter -->
      <div class="mb-4">
        <div class="field">
          <div class="flex gap-3 align-items-center">
            <div class="field">
              <label for="start-date" class="text-sm mb-1 block"
                >Fra dato:</label
              >
              <Calendar
                id="start-date"
                v-model="startDate"
                dateFormat="dd-mm-yy"
                placeholder="Vælg startdato"
                :showIcon="true"
                :manualInput="true"
                :minDate="minDate"
                :maxDate="maxDate"
                @date-select="onDateChange"
                @input="onDateChange"
              />
            </div>
            <div class="field">
              <label for="end-date" class="text-sm mb-1 block">Til dato:</label>
              <Calendar
                id="end-date"
                v-model="endDate"
                dateFormat="dd-mm-yy"
                placeholder="Vælg slutdato"
                :showIcon="true"
                :manualInput="true"
                :minDate="minDate"
                :maxDate="maxDate"
                @date-select="onDateChange"
                @input="onDateChange"
              />
            </div>
            <div class="field flex flex-column">
              <label class="text-sm mb-1 block" style="visibility: hidden">
                Placeholder
              </label>

              <div class="flex gap-2">
                <Button
                  label="Søg"
                  @click="executeSearch"
                  class="p-button-sm frai-buttons"
                  style="height: 2.5rem"
                />

                <Button
                  label="Nulstil til i dag"
                  @click="resetToToday"
                  class="p-button-outlined p-button-sm frai-buttons"
                  style="height: 2.5rem"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Download knapper samt global søgefunktion -->
      <div class="mb-4 flex justify-content-between align-items-center">
        <!-- Download knapper til venstre -->
        <JNDownloadOverblikComponent :filteredData="filteredOverblik" />

        <!-- Global søgefunktion til højre -->
        <div
          class="field flex align-items-center gap-3"
          style="margin-bottom: 0; min-width: 350px"
        >
          <label
            for="global-search"
            class="text font-semibold whitespace-nowrap"
            >Søg:</label
          >
          <InputText
            id="global-search"
            v-model="globalSearchInput"
            placeholder="Søg på tværs af alle kolonner..."
            class="w-full"
            style="min-width: 250px"
          />
        </div>
      </div>

      <!-- DataTable -->
      <FRAIDataTableExtended
        :data="filteredOverblik"
        :columns="tableColumns"
        paginator
        :rows="rowsPerPage"
        stripedRows
        filterDisplay="row"
        responsiveLayout="scroll"
        class="p-datatable-sm"
        tableStyle="table-layout: fixed; width: 100%;"
      >
        <!-- Filter slots for each column -->
        <template #filter-kr_initialer>
          <InputText
            v-model="filterInputs.kr_initialer"
            placeholder="Filtrer kunderådgiver"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-call_id>
          <InputText
            v-model="filterInputs.call_id"
            placeholder="Filtrer call ID"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-koe>
          <InputText
            v-model="filterInputs.koe"
            placeholder="Filtrer kø"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-load_time>
          <InputText
            v-model="filterInputs.load_time"
            placeholder="Filtrer tidspunkt"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-notat>
          <InputText
            v-model="filterInputs.notat"
            placeholder="Filtrer notat"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-feedback>
          <InputText
            v-model="filterInputs.feedback"
            placeholder="Filtrer feedback"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-ordning>
          <InputText
            v-model="filterInputs.ordning"
            placeholder="Filtrer ordning"
            class="p-column-filter"
            style="width: 100%"
          />
        </template>

        <template #filter-rating>
          <Dropdown
            v-model="filterInputs.rating"
            :options="ratingOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Vælg vurdering"
            class="p-column-filter"
            style="width: 100%"
            scrollHeight="240px"
          />
        </template>

        <template #filter-benyttet>
          <Dropdown
            v-model="filterInputs.benyttet"
            :options="benyttetOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Vælg..."
            class="p-column-filter"
            style="width: 100%"
          />
        </template>
      </FRAIDataTableExtended>

      <!-- Rækkeinfo -->
      <div class="mt-3 text-sm text-500 text-right">
        {{ paginationInfo }}
      </div>
    </div>
  </body>
</template>

<script lang="ts">
import { ref, computed, onBeforeMount, toRef, reactive } from "vue";
import { useDataStore } from "../stores/JNNotatOverblik";
import JNDownloadOverblikComponent from "./JNDownloadOverblikComponent.vue";
import { useToast } from "primevue/usetoast";

export default {
  components: {
    JNDownloadOverblikComponent,
  },
  setup() {
    const dataStore = useDataStore();
    const notater = toRef(dataStore, "notater");
    const toast = useToast();

    // Global søgefunktion
    const globalSearchInput = ref("");

    // Dato filter
    const startDate = ref(new Date()); // Default to today
    const endDate = ref(new Date()); // Default to today

    // Begræns datovælger til maksimalt 2 måneder tilbage
    const minDate = computed(() => {
      const today = new Date();
      const twoMonthsBack = new Date(today);
      twoMonthsBack.setMonth(today.getMonth() - 2);
      return twoMonthsBack;
    });

    // Begræns datovælger til maksimalt i dag
    const maxDate = computed(() => {
      return new Date(); // Today
    });

    // Række information
    const currentPage = ref(0); // 0-based
    const rowsPerPage = ref(40);

    // Kolonner i tabellen med header og styling
    const tableColumns = [
      {
        field: "kr_initialer",
        header: "Kunderådgiver",
        style: "width: 140px; min-width: 140px;",
        sortable: true,
        filter: true,
      },
      {
        field: "call_id",
        header: "Call ID",
        style: "width: 160px; min-width: 160px;",
        sortable: true,
        filter: true,
      },
      {
        field: "koe",
        header: "Kø",
        style: "width: 160px; min-width: 160px;",
        sortable: true,
        filter: true,
      },
      {
        field: "load_time",
        header: "Tidspunkt",
        style: "width: 110px; min-width: 110px;",
        sortable: true,
        filter: true,
        formatFunction: (index, field, value) => formatDateTime(value),
      },
      {
        field: "notat",
        header: "Notat",
        style: "width: 400px; min-width: 400px; white-space: pre-wrap;",
        sortable: true,
        filter: true,
        formatFunction: (index, field, value) => {
          if (!value) return "";

          let text = value;

          // Erstatter <br>, <br/>, <br /> med newlines
          text = text.replace(/<br\s*\/?>/gi, "\n");
          // Erstatter </p>, </div> med newlines
          text = text.replace(/<\/(p|div)>/gi, "\n");

          // Fjerner alle andre HTML tags
          text = text.replace(/<[^>]*>/g, "");

          // Decoder HTML entities
          const temp = document.createElement("div");
          temp.innerHTML = text;
          text = temp.textContent || temp.innerText || "";

          // Fjerner ekstra newlines men bevarer enkelte newlines
          text = text.replace(/\n\s*\n\s*\n/g, "\n\n").trim();

          return text;
        },
      },
      {
        field: "feedback",
        header: "Feedback",
        style: "width: 210px; min-width: 210px;",
        sortable: true,
        filter: true,
      },
      {
        field: "ordning",
        header: "Ordning",
        style: "width: 100px; min-width: 100px;",
        sortable: true,
        filter: true,
      },
      {
        field: "rating",
        header: "Vurdering",
        style: "width: 110px; min-width: 110px;",
        sortable: true,
        filter: true,
        formatFunction: (index, field, value) => {
          if (value === -1 || value === "-1") {
            return "--";
          }
          return `${"❤️".repeat(value)} ${value}/5`;
        },
      },
      {
        field: "benyttet",
        header: "Notat benyttet",
        style: "width: 140px; min-width: 140px;",
        sortable: true,
        filter: true,
        formatFunction: (index, field, value) => {
          if (value === null || value === undefined) return "--";
          if (value === 1 || value === "1" || value === true) return "Ja";
          if (value === 0 || value === "0" || value === false) return "Nej";
          return "--";
        },
      },
    ];

    // Rating filter
    const ratingOptions = [
      { label: "Alle", value: "" },
      { label: "1", value: "1" },
      { label: "2", value: "2" },
      { label: "3", value: "3" },
      { label: "4", value: "4" },
      { label: "5", value: "5" },
    ];

    // Notat benyttet filter
    const benyttetOptions = [
      { label: "Alle", value: "" },
      { label: "Ja", value: "1" }, // 1 = benyttet
      { label: "Nej", value: "0" }, // 0 = ikke benyttet
    ];

    // Reaktive filter input
    const filterInputs = reactive({
      kr_initialer: "",
      call_id: "",
      koe: "",
      load_time: "",
      notat: "",
      feedback: "",
      ordning: "",
      rating: "",
      benyttet: "",
    });

    onBeforeMount(async () => {
      /* 
      Hent notater fra API
      */
      await dataStore.fetchNotatData(true); // Bruger historik fra i dag som default
    });

    const onDateChange = () => {
      /*
      Tilpasser slutdato hvis startdato er større
      */
      if (endDate.value < startDate.value) {
        endDate.value = new Date(startDate.value);
        toast.add({
          severity: "info",
          summary: "Ugyldig dato",
          detail: "Slutdato er blevet justeret til at matche startdato",
          life: 3000,
        });
      }
    };

    const isSameDay = (date1: Date, date2: Date) => {
      /*
      Tjekker om start- og slutdato er ens
      */
      return date1.toDateString() === date2.toDateString();
    };

    const executeSearch = async () => {
      const isToday =
        isSameDay(startDate.value, new Date()) &&
        isSameDay(endDate.value, new Date());

      await dataStore.fetchNotatData(isToday);
    };

    const resetToToday = async () => {
      /*
      Nulstiller til dags dato
      */
      const today = new Date();
      startDate.value = today;
      endDate.value = today;
      await dataStore.fetchNotatData(true);
    };

    const filteredOverblik = computed(() => {
      /* 
      Filtrerer notater ud fra brugerinput
      */
      if (!notater.value?.notater || !Array.isArray(notater.value.notater))
        return [];

      const notatValues = notater.value.notater;

      return notatValues
        .filter((row: any) => {
          // Dato filter
          const rowDate = new Date(row.load_time);
          const start = new Date(startDate.value);
          const end = new Date(endDate.value);

          // Sætter klokkeslet for start- og slutdato
          start.setHours(0, 0, 0, 0);
          end.setHours(23, 59, 59, 999);

          const dateMatch = rowDate >= start && rowDate <= end;

          // Global søgefunktion
          const globalMatch =
            !globalSearchInput.value ||
            Object.values(row).some((value: any) =>
              value
                ?.toString()
                .toLowerCase()
                .includes(globalSearchInput.value.toLowerCase()),
            );

          // Filter på kolonneniveau
          const columnMatches = Object.keys(filterInputs).every((field) => {
            const filterValue =
              filterInputs[field as keyof typeof filterInputs];
            if (!filterValue) return true;

            const rowValue = row[field];
            if (field === "rating") {
              return rowValue?.toString() === filterValue;
            } else if (field === "benyttet") {
              return rowValue?.toString() === filterValue;
            } else if (field === "load_time") {
              // For tidspunktet tjekkes mod formatet vist i frontend
              const formattedDate = formatDateTime(rowValue);
              return formattedDate
                .toLowerCase()
                .includes(filterValue.toLowerCase());
            }
            return rowValue?.toLowerCase().includes(filterValue.toLowerCase());
          });

          return dateMatch && globalMatch && columnMatches;
        })
        .sort((a, b) => {
          const dateA = new Date(a.load_time);
          const dateB = new Date(b.load_time);
          return dateB.getTime() - dateA.getTime();
        });
    });

    const formatDateTime = (dateTime: string) => {
      /*
      Får en dato som input og tilpasser det til dansk tid og
      formaterer det til at være "dd-mm-yyyy hh:mm:ss"
      */
      if (!dateTime) return "";
      try {
        const date = new Date(dateTime);
        // Indstil til rigtige tidszone
        date.setHours(date.getHours() - 2);

        // Formater som dd-mm-yyyy HH:MM:SS
        const day = date.getDate().toString().padStart(2, "0");
        const month = (date.getMonth() + 1).toString().padStart(2, "0");
        const year = date.getFullYear();
        const hours = date.getHours().toString().padStart(2, "0");
        const minutes = date.getMinutes().toString().padStart(2, "0");
        const seconds = date.getSeconds().toString().padStart(2, "0");

        return `${day}-${month}-${year} ${hours}:${minutes}:${seconds}`;
      } catch {
        return dateTime;
      }
    };

    const paginationInfo = computed(() => {
      /*
      Funktion til at beksrive antal rækker som ses i tabellen
      ud af det totale antal rækker
      */
      const totalRows = filteredOverblik.value.length;
      if (totalRows === 0) return "Viser 0 rækker";

      const startRow = currentPage.value * rowsPerPage.value + 1;
      const endRow = Math.min(
        (currentPage.value + 1) * rowsPerPage.value,
        totalRows,
      );

      return `Viser ${startRow}-${endRow} ud af ${totalRows} rækker`;
    });

    // Tilpas rækkeinfo ved events
    const onPageChange = (event: any) => {
      currentPage.value = event.page;
    };

    return {
      filteredOverblik,
      globalSearchInput,
      startDate,
      endDate,
      minDate,
      maxDate,
      filterInputs,
      tableColumns,
      ratingOptions,
      benyttetOptions,
      formatDateTime,
      onDateChange,
      executeSearch,
      resetToToday,
      currentPage,
      rowsPerPage,
      paginationInfo,
      onPageChange,
    };
  },
};
</script>

<style scoped>
/* Skjul kolonnefilterets clear-knap */
:deep(.p-column-filter-clear-button) {
  display: none;
}

/* Skjul filter ikoner */
:deep(.p-datatable .p-column-filter-menu-button) {
  display: none !important;
}
</style>
