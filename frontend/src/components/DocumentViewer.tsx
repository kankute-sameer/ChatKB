import { useEffect, useMemo, useRef, useState } from "react";
import { X, ZoomIn, ZoomOut } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "@/components/ui/button";
import {
  calculateOverlay,
  type OverlayRect,
} from "@/components/document-viewer-math";
import { getToken } from "@/lib/api";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

/** Directory URL for OpenJPEG / QCMS wasm (needed for JPEG 2000 figures in many textbooks). */
const PDF_WASM_URL = new URL(
  "pdfjs-dist/wasm/openjpeg.wasm",
  import.meta.url,
)
  .toString()
  .replace(/[^/]+$/, "");

const PDF_OPTIONS = { wasmUrl: PDF_WASM_URL };

export type NormalizedBbox = [number, number, number, number];

export interface DocumentViewerProps {
  fileId: string;
  /** When set, focuses a single page (citation mode). Omit to browse the whole PDF. */
  page?: number;
  bbox?: number[];
  regions?: number[][];
  filename: string;
  onClose: () => void;
}

export function DocumentViewer({
  fileId,
  page,
  bbox = [],
  regions,
  filename,
  onClose,
}: DocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(800);
  const [zoom, setZoom] = useState(1);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [numPages, setNumPages] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const citeMode = page != null;

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const update = () => {
      setContainerWidth(Math.max(320, element.clientWidth - 48));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const file = useMemo(() => {
    const token = getToken();
    return {
      url: `/api/v1/files/${encodeURIComponent(fileId)}/content`,
      httpHeaders: token ? { Authorization: `Bearer ${token}` } : undefined,
    };
  }, [fileId]);

  const renderWidth = Math.round(containerWidth * zoom);
  const boxes = regions?.length ? regions : [bbox];
  const overlays = citeMode
    ? boxes
        .map((region) =>
          calculateOverlay(region, pageSize.width, pageSize.height),
        )
        .filter((rect): rect is OverlayRect => rect !== null)
    : [];

  const pageNumbers = citeMode
    ? [Math.max(1, page)]
    : Array.from({ length: numPages }, (_, index) => index + 1);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={citeMode ? `${filename}, page ${page}` : filename}
      className="fixed inset-y-0 right-0 z-[70] flex w-full flex-col border-l border-border bg-gray-100 shadow-2xl md:w-[clamp(36rem,60vw,64rem)]"
    >
      <div className="flex items-center gap-3 border-b border-border bg-white px-4 py-3 text-ink">
        <div className="min-w-0 flex-1">
          <p className="truncate font-sans text-nav font-ui font-medium">
            {filename}
          </p>
          {citeMode ? (
            <p className="text-xs text-ink-muted">Page {page}</p>
          ) : numPages > 0 ? (
            <p className="text-xs text-ink-muted">
              {numPages} page{numPages === 1 ? "" : "s"}
            </p>
          ) : null}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Zoom out"
          onClick={() => setZoom((value) => Math.max(0.5, value - 0.25))}
        >
          <ZoomOut className="size-4" />
        </Button>
        <span className="w-12 text-center text-xs text-ink-muted">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Zoom in"
          onClick={() => setZoom((value) => Math.min(2.5, value + 0.25))}
        >
          <ZoomIn className="size-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Close document"
          onClick={onClose}
        >
          <X className="size-5" />
        </Button>
      </div>

      <div ref={containerRef} className="min-h-0 flex-1 overflow-auto p-6">
        <div className="mx-auto flex w-fit flex-col gap-6">
          <Document
            file={file}
            options={PDF_OPTIONS}
            loading={
              <div className="flex h-96 w-[40rem] items-center justify-center bg-white text-sm text-gray-500">
                Loading PDF…
              </div>
            }
            error={
              <div className="flex h-96 w-[40rem] items-center justify-center bg-white p-8 text-sm text-red-700">
                {error ?? "Could not load this PDF."}
              </div>
            }
            onLoadSuccess={(doc) => setNumPages(doc.numPages)}
            onLoadError={(loadError) => setError(loadError.message)}
          >
            {pageNumbers.map((pageNumber) => (
              <div
                key={pageNumber}
                className="relative bg-white shadow-2xl"
              >
                <Page
                  pageNumber={pageNumber}
                  width={renderWidth}
                  renderAnnotationLayer={false}
                  renderTextLayer
                  onRenderSuccess={(pdfPage) => {
                    if (!citeMode || pageNumber !== page) return;
                    const viewport = pdfPage.getViewport({ scale: 1 });
                    const scale = renderWidth / viewport.width;
                    setPageSize({
                      width: renderWidth,
                      height: viewport.height * scale,
                    });
                  }}
                />
                {citeMode && pageNumber === page
                  ? overlays.map((rect, index) => (
                      <div
                        key={`${rect.left}-${rect.top}-${index}`}
                        aria-hidden
                      >
                        <div
                          className="pointer-events-none absolute"
                          style={{
                            ...rect,
                            backgroundColor: "rgb(252, 232, 172)",
                            mixBlendMode: "multiply",
                          }}
                        />
                        <div
                          className="pointer-events-none absolute"
                          style={{
                            ...rect,
                            border: "1.5px solid rgb(252, 232, 172)",
                          }}
                        />
                      </div>
                    ))
                  : null}
              </div>
            ))}
          </Document>
        </div>
      </div>
    </div>
  );
}
