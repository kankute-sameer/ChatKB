import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const TOUR_SLIDES = [
  {
    title: "Welcome!",
    body: "Build agents, give them tools and knowledge, and chat. Every answer is cited.",
  },
  {
    title: "Create an agent",
    body: "Describe what you want and the builder sets it up — name, instructions, tools. Edit it anytime.",
  },
  {
    title: "Web search",
    body: "Ask anything current. The agent searches the web and cites what it finds.",
  },
  {
    title: "Knowledge base",
    body: "Upload PDF, DOCX, TXT, MD, CSV, or JSON and attach it to an agent. Citations open the exact page, highlighted. Tables can be queried directly.",
  },
  {
    title: "Feedback Please",
    body: "You will find a feedback button in the bottom left corner of the screen. Please use it to let me know what you think.",
  },
] as const;

interface ProductTourDialogProps {
  open: boolean;
  onClose: () => void;
}

export function ProductTourDialog({
  open,
  onClose,
}: ProductTourDialogProps) {
  const [slideIndex, setSlideIndex] = useState(0);
  const slide = TOUR_SLIDES[slideIndex];

  useEffect(() => {
    if (open) setSlideIndex(0);
  }, [open]);

  const next = () => {
    if (slideIndex === TOUR_SLIDES.length - 1) {
      onClose();
      return;
    }
    setSlideIndex((current) => current + 1);
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="w-[min(720px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-10">
        <DialogHeader>
          <DialogTitle className="text-title font-normal">
            {slide.title}
          </DialogTitle>
        </DialogHeader>

        <div className="mt-8 flex min-h-[20rem] items-center justify-center rounded-xl border border-white bg-white px-10 py-12">
          <p className="max-w-xl text-center font-sans text-nav font-ui text-ink-muted">
            {slide.body}
          </p>
        </div>

        <div className="mt-6 flex items-center justify-between">
          <div
            className="flex items-center gap-2"
            aria-label={`Slide ${slideIndex + 1} of ${TOUR_SLIDES.length}`}
          >
            {TOUR_SLIDES.map((item, index) => (
              <span
                key={item.title}
                aria-current={index === slideIndex ? "step" : undefined}
                className={cn(
                  "size-2 rounded-full transition-colors duration-color ease-out",
                  index === slideIndex ? "bg-gray-900" : "bg-gray-300",
                )}
              />
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              className="rounded-full px-6"
              disabled={slideIndex === 0}
              onClick={() => setSlideIndex((current) => current - 1)}
            >
              Back
            </Button>
            <Button
              type="button"
              className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
              onClick={next}
            >
              Next
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
