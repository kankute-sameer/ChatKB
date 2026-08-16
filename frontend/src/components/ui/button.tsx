import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded transition-colors duration-color ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-gray-200",
        outline:
          "border border-border bg-background hover:bg-muted text-foreground",
        ghost: "hover:bg-muted text-foreground",
        accent: "bg-accent-muted text-accent hover:bg-accent-muted",
      },
      size: {
        default: "h-row px-4 text-nav",
        sm: "h-8 px-3 text-nav",
        lg: "h-row px-5 text-nav",
        icon: "size-8",
        pill: "h-row px-4 rounded-full text-nav",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), "font-ui", className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
