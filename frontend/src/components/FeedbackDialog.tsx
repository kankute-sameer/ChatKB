import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { submitExperienceFeedback } from "@/lib/feedback";

interface FeedbackDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FeedbackDialog({
  open,
  onOpenChange,
}: FeedbackDialogProps) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (submitting) return;
    setComment("");
    setError(null);
    onOpenChange(false);
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const value = comment.trim();
    if (!value || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitExperienceFeedback(value);
      setComment("");
      onOpenChange(false);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not send feedback. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          close();
          return;
        }
        onOpenChange(true);
      }}
    >
      <DialogContent className="w-[min(620px,calc(100vw-4rem))] max-w-none rounded-lg px-8 py-10">
        <DialogHeader>
          <DialogTitle className="text-title font-normal">
            How has your experience been?
          </DialogTitle>
          <p className="mt-2 font-sans text-nav font-ui text-ink-muted">
            Share what is working well or what we could improve.
          </p>
        </DialogHeader>

        <form
          className="mt-8 flex flex-col gap-5 font-sans text-nav font-ui"
          onSubmit={(event) => void onSubmit(event)}
        >
          <label className="flex flex-col gap-2">
            <span className="text-ink">Feedback</span>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="Tell us about your experience..."
              rows={5}
              maxLength={2000}
              autoFocus
              disabled={submitting}
              className="flex min-h-32 w-full resize-none rounded-lg border border-input bg-background px-3 py-3 font-sans text-nav font-ui text-foreground placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </label>

          {error ? <p className="text-destructive">{error}</p> : null}

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              className="rounded-full"
              disabled={submitting}
              onClick={close}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="rounded-full bg-gray-900 px-6 text-white hover:bg-gray-800"
              disabled={submitting || !comment.trim()}
            >
              {submitting ? "Sending…" : "Send feedback"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
