<!--
JNDownloadOverblikComponent
________________________________________________________________________________________

Denne komponent giver brugeren mulighed for at downloade eller kopiere 
notatoverblikket i forskellige formater.
________________________________________________________________________________________

Funktionaliteter:
- Kopiér data til clipboard
- Download som Excel (.xlsx)
- Download som CSV (.csv)
- Download som PDF (.pdf)

Props:
- filteredData: Array med filtreret data fra parent komponenten
-->

<template>
  <div class="download-buttons-container">
    <div class="download-buttons">
      <Button
        label="Kopiér"
        icon="pi pi-copy"
        class="p-button-outlined p-button-secondary frai-buttons"
        @click="copyToClipboard"
        :loading="copying"
        v-tooltip.top="'Kopiér data til udklipsholder'"
      />

      <Button
        label="Excel"
        icon="pi pi-file-excel"
        class="p-button-outlined p-button-success frai-buttons"
        @click="downloadExcel"
        :loading="downloadingExcel"
        v-tooltip.top="'Download data som Excel fil (.xlsx)'"
      />

      <Button
        label="CSV"
        icon="pi pi-file"
        class="p-button-outlined p-button-info frai-buttons"
        @click="downloadCSV"
        :loading="downloadingCSV"
        v-tooltip.top="'Download data som CSV fil (.csv)'"
      />

      <Button
        label="PDF"
        icon="pi pi-file-pdf"
        class="p-button-outlined p-button-danger frai-buttons"
        @click="downloadPDF"
        :loading="downloadingPDF"
        v-tooltip.top="'Download data som PDF fil (.pdf)'"
      />
    </div>

    <!-- Toast for feedback -->
    <Toast />
  </div>
</template>

<script lang="ts">
import { ref } from "vue";
import { useToast } from "primevue/usetoast";
import { NotaterData } from "../types";
import * as XLSX from "xlsx";
import jsPDF from "jspdf";

export default {
  props: {
    filteredData: {
      type: Array as () => NotaterData[],
      required: true,
      default: () => [],
    },
  },
  setup(props: { filteredData: NotaterData[] }) {
    const toast = useToast();

    // Loading states
    const copying = ref(false);
    const downloadingExcel = ref(false);
    const downloadingCSV = ref(false);
    const downloadingPDF = ref(false);

    const formatDateTime = (dateTime: any) => {
      /*
      Får en dato som input og tilpasser det til dansk tid og
      formaterer det til at være "dd-mm-yyyy hh:mm:ss"
      */
      if (!dateTime) return "";
      try {
        const date = new Date(dateTime);
        // Indstil til rigtige tidszone
        date.setHours(date.getHours() - 2);

        // Formater som dd-mm-yyyy HH:mm:ss
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

    // Formaterer data til rigtige formater
    const formatDataForExport = (exportType = "default") => {
      /*
      Funktion til at formatere data til export
      exportType: 'pdf' for PDF export (strips HTML), 'default' for others (keeps HTML)
      */
      return props.filteredData.map((row) => ({
        Kunderådgiver: row.kr_initialer || "",
        "Call ID": row.call_id || "",
        Kø: row.koe || "",
        Tidspunkt: formatDateTime(row.load_time),
        Notat: stripHtml(row.notat || "", exportType),
        Feedback: row.feedback || "Ingen feedback",
        Ordning: row.ordning || "",
        Vurdering: row.rating || "",
      }));
    };

    const stripHtml = (html, exportType) => {
      /*
      Funktion til at fjerne HTML tags fra tekst (til PDF export)
      */
      if (!html) return "";
      // Erstatter <br>, <br/>, <br /> med newlines
      let text = html.replace(/<br\s*\/?>/gi, "\n");
      // Erstatter </p>, </div> med newlines
      text = text.replace(/<\/(p|div)>/gi, "\n");
      // Fjerner alle andre HTML tags
      text = text.replace(/<[^>]*>/g, "");
      // Decoder HTML entities
      const temp = document.createElement("div");
      temp.innerHTML = text;
      text = temp.textContent || temp.innerText || "";
      if (exportType === "csv" || exportType === "clipboard") {
        // For CSV og clipboard: erstat newlines med mellemrum
        text = text.replace(/\n+/g, " ");
        text = text.replace(/\s+/g, " ");
      } else {
        // For andre exports: Behold newline men fjern overflødelige
        text = text.replace(/\n\s*\n\s*\n/g, "\n\n"); // Flere newlines -> dobbelt newline
        text = text.replace(/[ \t]+/g, " "); // Normaliserer kun mellemrum og tabs, ikke newlines
      }
      text = text.trim();
      return text;
    };

    const copyToClipboard = async () => {
      /*
      Funktion til at kopiere data til clipboardet
      */
      copying.value = true;
      try {
        const formattedData = formatDataForExport("clipboard"); // Keep HTML for clipboard

        // Opretter værdier  til clipboardet
        const headerRow = Object.keys(formattedData[0] || {}).join("\t");
        const dataRows = formattedData
          .map((row) => Object.values(row).join("\t"))
          .join("\n");

        const clipboardText = headerRow + "\n" + dataRows;

        await navigator.clipboard.writeText(clipboardText);

        toast.add({
          severity: "success",
          summary: "Kopieret",
          detail: `${formattedData.length} rækker kopieret til clipboard`,
          life: 3000,
        });
      } catch (error) {
        toast.add({
          severity: "error",
          summary: "Fejl",
          detail: "Kunne ikke kopiere data",
          life: 3000,
        });
      } finally {
        copying.value = false;
      }
    };

    const downloadExcel = () => {
      /*
      Funktion til at downloade data som excel
      */
      downloadingExcel.value = true;
      try {
        const formattedData = formatDataForExport("excel"); // Keep HTML for Excel

        const worksheet = XLSX.utils.json_to_sheet(formattedData);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Notater");

        // Auto-size kolonner
        const colWidths = Object.keys(formattedData[0] || {}).map((key) => ({
          wch: Math.max(key.length, 15),
        }));
        worksheet["!cols"] = colWidths;

        const fileName = `notat_overblik_${new Date().toISOString().split("T")[0]}.xlsx`;
        XLSX.writeFile(workbook, fileName);

        toast.add({
          severity: "success",
          summary: "Excel downloaded",
          detail: `${fileName} er downloaded`,
          life: 3000,
        });
      } catch (error) {
        toast.add({
          severity: "error",
          summary: "Fejl",
          detail: "Kunne ikke downloade Excel fil",
          life: 3000,
        });
      } finally {
        downloadingExcel.value = false;
      }
    };

    const downloadCSV = () => {
      /*
      Funktion til at downloade data som csv
      */
      downloadingCSV.value = true;
      try {
        const formattedData = formatDataForExport("csv"); // Keep HTML for CSV

        const headerRow = Object.keys(formattedData[0] || {}).join(",");
        const dataRows = formattedData
          .map((row) =>
            Object.values(row)
              .map((value) => `"${String(value).replace(/"/g, '""')}"`)
              .join(","),
          )
          .join("\n");

        const csvContent = headerRow + "\n" + dataRows;

        // Tilføjer UTF-8 BOM for at kunne læse danske karakterer
        const BOM = "\uFEFF";
        const csvWithBOM = BOM + csvContent;

        const blob = new Blob([csvWithBOM], {
          type: "text/csv;charset=utf-8;",
        });

        const fileName = `notat_overblik_${new Date().toISOString().split("T")[0]}.csv`;
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = fileName;
        link.click();

        toast.add({
          severity: "success",
          summary: "CSV downloaded",
          detail: `${fileName} er downloaded`,
          life: 3000,
        });
      } catch (error) {
        toast.add({
          severity: "error",
          summary: "Fejl",
          detail: "Kunne ikke downloade CSV fil",
          life: 3000,
        });
      } finally {
        downloadingCSV.value = false;
      }
    };

    const downloadPDF = () => {
      /*
      Funktion til at downloade data som pdf
      */
      downloadingPDF.value = true;
      try {
        const formattedData = formatDataForExport("pdf"); // Strip HTML for PDF

        const doc = new jsPDF("l", "mm", "a4"); // Landscape orientation

        // Opretter tabel med wordwraping
        const headers = Object.keys(formattedData[0] || {});
        const startY = 15;
        const baseRowHeight = 6;
        const colWidths = [25, 25, 20, 30, 80, 50, 25, 18]; // Column widths in mm
        let currentY = startY;

        // Tekststørrelse
        doc.setFontSize(8);

        // Hjælpefunktion til at splitte linjer, så det passer kolonnestørrelsen
        const splitTextToFit = (text: string, maxWidth: number) => {
          if (!text) return [""];

          // Håndterer newlines fra stripped HTML
          const paragraphs = String(text).split("\n");
          const allLines = [];

          paragraphs.forEach((paragraph) => {
            if (!paragraph.trim()) {
              allLines.push(""); // Tom linje
              return;
            }

            const words = paragraph.trim().split(" ");
            let currentLine = "";

            for (const word of words) {
              const testLine = currentLine ? `${currentLine} ${word}` : word;
              const testWidth = doc.getTextWidth(testLine);

              if (testWidth <= maxWidth - 4) {
                // 4mm padding
                currentLine = testLine;
              } else {
                if (currentLine) {
                  allLines.push(currentLine);
                  currentLine = word;
                } else {
                  // Deler ord op, hvis det er for langt
                  let remainingWord = word;
                  while (remainingWord.length > 0) {
                    let partialWord = "";
                    for (let i = 1; i <= remainingWord.length; i++) {
                      if (
                        doc.getTextWidth(remainingWord.substring(0, i)) <=
                        maxWidth - 4
                      ) {
                        partialWord = remainingWord.substring(0, i);
                      } else {
                        break;
                      }
                    }
                    if (partialWord.length === 0)
                      partialWord = remainingWord.charAt(0);
                    allLines.push(partialWord);
                    remainingWord = remainingWord.substring(partialWord.length);
                  }
                  currentLine = "";
                }
              }
            }

            if (currentLine) {
              allLines.push(currentLine);
            }
          });

          return allLines.length > 0 ? allLines : [""];
        };

        // Tegner streger ved header
        let currentX = 14;
        doc.setFont(undefined, "bold");
        headers.forEach((header, index) => {
          doc.rect(currentX, currentY, colWidths[index], baseRowHeight);
          doc.text(header, currentX + 2, currentY + 4);
          currentX += colWidths[index];
        });

        currentY += baseRowHeight;
        doc.setFont(undefined, "normal");

        // Tegner rækkestreger
        formattedData.forEach((row) => {
          // Beregner rækkehøjden baseret på celleværdier
          const rowLines = Object.values(row).map((value, colIndex) =>
            splitTextToFit(String(value || ""), colWidths[colIndex]),
          );

          const maxLines = Math.max(...rowLines.map((lines) => lines.length));
          const rowHeight = Math.max(baseRowHeight, maxLines * 3.5 + 2); // Add 2mm padding at bottom

          // Tjekker om det er en ny side
          if (currentY + rowHeight > 180) {
            doc.addPage();
            currentY = 20;
          }

          // Tegner border
          currentX = 14;
          headers.forEach((header, colIndex) => {
            doc.rect(currentX, currentY, colWidths[colIndex], rowHeight);
            currentX += colWidths[colIndex];
          });

          // Skriver tekst
          currentX = 14;
          Object.values(row).forEach((value, colIndex) => {
            const lines = rowLines[colIndex];
            lines.forEach((line, lineIndex) => {
              const textY = currentY + 4 + lineIndex * 3.5; // 3.5mm line spacing
              doc.text(line, currentX + 2, textY);
            });
            currentX += colWidths[colIndex];
          });

          currentY += rowHeight;
        });

        const fileName = `notat_overblik_${new Date().toISOString().split("T")[0]}.pdf`;
        doc.save(fileName);

        toast.add({
          severity: "success",
          summary: "PDF downloaded",
          detail: `${fileName} er downloaded`,
          life: 3000,
        });
      } catch (error) {
        console.error("PDF Error:", error);
        toast.add({
          severity: "error",
          summary: "Fejl",
          detail: "Kunne ikke downloade PDF fil",
          life: 3000,
        });
      } finally {
        downloadingPDF.value = false;
      }
    };

    return {
      copying,
      downloadingExcel,
      downloadingCSV,
      downloadingPDF,
      copyToClipboard,
      downloadExcel,
      downloadCSV,
      downloadPDF,
    };
  },
};
</script>

<style scoped>
.download-buttons-container {
  margin-bottom: 1rem;
}

.download-buttons {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  align-items: center;
}

@media (max-width: 768px) {
  .download-buttons {
    flex-direction: column;
    width: 100%;
  }

  .download-buttons .p-button {
    width: 100%;
    justify-content: center;
  }
}

.p-button {
  min-width: 120px;
}
</style>
