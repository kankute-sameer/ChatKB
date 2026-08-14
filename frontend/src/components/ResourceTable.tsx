import type { KeyboardEvent, ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface ResourceColumn<T> {
  id: string;
  header: string;
  className?: string;
  render: (row: T) => ReactNode;
}

interface ResourceTableProps<T> {
  rows: T[];
  columns: ResourceColumn<T>[];
  getRowId: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function ResourceTable<T>({
  rows,
  columns,
  getRowId,
  onRowClick,
  emptyMessage = "Nothing here yet.",
}: ResourceTableProps<T>) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((column) => (
            <TableHead key={column.id} className={column.className}>
              {column.header}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.length === 0 ? (
          <TableRow>
            <TableCell
              colSpan={columns.length}
              className="py-8 text-center text-muted-foreground"
            >
              {emptyMessage}
            </TableCell>
          </TableRow>
        ) : (
          rows.map((row) => (
            <TableRow
              key={getRowId(row)}
              className={onRowClick ? "cursor-pointer" : undefined}
              onClick={() => onRowClick?.(row)}
              onKeyDown={(event: KeyboardEvent<HTMLTableRowElement>) => {
                if (onRowClick && event.key === "Enter") onRowClick(row);
              }}
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => (
                <TableCell key={column.id} className={column.className}>
                  {column.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
