import csvIcon from "@/assets/csv.svg";
import docxIcon from "@/assets/docx.png";
import jsonIcon from "@/assets/json.svg";
import markdownIcon from "@/assets/markdown.svg";
import pdfIcon from "@/assets/pdf.png";
import txtIcon from "@/assets/txt.png";
import { cn } from "@/lib/utils";

const ICONS: Record<string, string> = {
  pdf: pdfIcon,
  docx: docxIcon,
  txt: txtIcon,
  md: markdownIcon,
  markdown: markdownIcon,
  csv: csvIcon,
  tsv: csvIcon,
  json: jsonIcon,
};

export function FileTypeIcon({
  filename,
  className,
}: {
  filename: string;
  className?: string;
}) {
  const extension = filename.split(".").pop()?.toLowerCase() ?? "";
  const icon = ICONS[extension] ?? txtIcon;
  return (
    <img
      src={icon}
      alt={`${extension.toUpperCase() || "File"} file`}
      className={cn("shrink-0 object-contain", className)}
    />
  );
}
