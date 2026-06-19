<template>
  <div class="frai-table-wrapper">
    <table class="frai-table" :style="tableStyle">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.field" :style="column.style">
            {{ column.header }}
          </th>
        </tr>
        <tr v-if="hasFilterSlots">
          <th v-for="column in columns" :key="`${column.field}-filter`" :style="column.style">
            <slot :name="`filter-${column.field}`" />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in pagedData" :key="row.call_id ?? row.id ?? index">
          <td v-for="column in columns" :key="`${row.call_id ?? index}-${column.field}`" :style="column.style">
            <div class="cell-content">{{ formatValue(column, row, index) }}</div>
          </td>
        </tr>
        <tr v-if="pagedData.length === 0">
          <td :colspan="columns.length" class="empty-state">Ingen data</td>
        </tr>
      </tbody>
    </table>

    <div v-if="paginator && totalPages > 1" class="pagination">
      <button type="button" class="page-button" :disabled="page === 0" @click="setPage(page - 1)">
        Forrige
      </button>
      <span>Side {{ page + 1 }} / {{ totalPages }}</span>
      <button type="button" class="page-button" :disabled="page >= totalPages - 1" @click="setPage(page + 1)">
        Næste
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, useSlots, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    data?: any[];
    columns?: any[];
    paginator?: boolean;
    rows?: number;
    tableStyle?: string;
  }>(),
  {
    data: () => [],
    columns: () => [],
    paginator: false,
    rows: 40,
    tableStyle: "",
  },
);

const emit = defineEmits(["page"]);
const slots = useSlots();
const page = ref(0);

const hasFilterSlots = computed(() =>
  props.columns.some((column: any) => Boolean(slots[`filter-${column.field}`])),
);

const totalPages = computed(() => {
  if (!props.paginator) {
    return 1;
  }
  return Math.max(1, Math.ceil(props.data.length / props.rows));
});

const pagedData = computed(() => {
  if (!props.paginator) {
    return props.data;
  }

  const start = page.value * props.rows;
  return props.data.slice(start, start + props.rows);
});

watch(
  () => props.data.length,
  () => {
    if (page.value >= totalPages.value) {
      page.value = Math.max(0, totalPages.value - 1);
    }
    emit("page", { page: page.value });
  },
  { immediate: true },
);

const setPage = (nextPage: number) => {
  page.value = Math.min(Math.max(nextPage, 0), totalPages.value - 1);
  emit("page", { page: page.value });
};

const formatValue = (column: any, row: any, index: number) => {
  const value = row?.[column.field];
  if (typeof column.formatFunction === "function") {
    return column.formatFunction(index, column.field, value);
  }
  return value ?? "";
};
</script>

<style scoped>
.frai-table-wrapper {
  overflow-x: auto;
}

.frai-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}

.frai-table th,
.frai-table td {
  padding: 0.75rem;
  border: 1px solid #d9dee7;
  text-align: left;
  vertical-align: top;
}

.frai-table th {
  background: #eef3f8;
}

.cell-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.empty-state {
  text-align: center;
  color: #6b7280;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1rem;
}

.page-button {
  padding: 0.5rem 0.75rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.375rem;
  background: #fff;
  cursor: pointer;
}

.page-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
