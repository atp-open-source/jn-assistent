import { ref } from "vue";
import { defineStore } from "pinia";
import axios from "axios";

export const useDataStore = defineStore("datastore", () => {
  const notater = ref({});

  async function fetchNotatData(dagens_historik = true) {
    /*
     Henter notat data fra serveren. Det er muligt at give en parameter 
      for at angive, hvorvidt det kun er dagens historik der skal inkluderes
    */
    try {
      const response = await axios.get("/web/jn/notat_oversigt_fe", {
        params: { dagens_historik },
      });

      // Konverterer load_time til Date objekter, hvis de findes
      if (
        response.data &&
        response.data.notater &&
        Array.isArray(response.data.notater)
      ) {
        response.data.notater.forEach((notat: any) => {
          if (notat.load_time) {
            notat.load_time = new Date(notat.load_time);
          }
        });
      }

      notater.value = response.data;
    } catch (error) {
      const status = (error as any).response
        ? (error as any).response.status
        : undefined;
      if (status === 500) {
        console.error("Internal Server Error");
      } else {
        console.error("Error fetching notater data:", error);
      }
      // Notater nulstilles ved fejl for at undgå at vise gammel data
      notater.value = {};
    }
  }

  return {
    notater,
    fetchNotatData,
  };
});
