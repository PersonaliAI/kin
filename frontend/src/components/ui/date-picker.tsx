"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/utils";

export function DatePicker({
  value,
  onChange,
  placeholder = "Pick a date",
  disabled = false,
  className,
}: {
  value: string | null | undefined;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Parse YYYY-MM-DD input value to Date object
  const selectedDate = useMemo(() => {
    if (!value) return null;
    const parts = value.split("-");
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      if (!isNaN(year) && !isNaN(month) && !isNaN(day)) {
        return new Date(year, month, day);
      }
    }
    return null;
  }, [value]);

  // Track the month/year currently visible in the calendar grid
  const [currentMonth, setCurrentMonth] = useState(() => selectedDate ?? new Date());

  // Keep grid view in sync with selectedDate when opened
  useEffect(() => {
    if (open && selectedDate) {
      setCurrentMonth(selectedDate);
    }
  }, [open, selectedDate]);

  // Close popover on click outside
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const monthYearLabel = useMemo(() => {
    return currentMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }, [currentMonth]);

  const daysGrid = useMemo(() => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();

    // First day of current month (0 = Sunday, 1 = Monday, ...)
    const firstDayIndex = new Date(year, month, 1).getDay();
    // Number of days in current month
    const totalDays = new Date(year, month + 1, 0).getDate();
    // Number of days in previous month
    const prevTotalDays = new Date(year, month, 0).getDate();

    const days: { date: Date; currentMonth: boolean; key: string }[] = [];

    // Pad from previous month
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const day = prevTotalDays - i;
      const date = new Date(year, month - 1, day);
      days.push({
        date,
        currentMonth: false,
        key: `prev-${day}`,
      });
    }

    // Days of current month
    for (let day = 1; day <= totalDays; day++) {
      const date = new Date(year, month, day);
      days.push({
        date,
        currentMonth: true,
        key: `curr-${day}`,
      });
    }

    // Pad for next month to complete the row (usually 6 rows total, 42 cells)
    const remainingCells = 42 - days.length;
    for (let day = 1; day <= remainingCells; day++) {
      const date = new Date(year, month + 1, day);
      days.push({
        date,
        currentMonth: false,
        key: `next-${day}`,
      });
    }

    return days;
  }, [currentMonth]);

  function prevMonth() {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  }

  function nextMonth() {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  }

  function selectDay(date: Date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    onChange(`${y}-${m}-${d}`);
    setOpen(false);
  }

  function clearDate(e: React.MouseEvent) {
    e.stopPropagation();
    onChange("");
  }

  const isToday = (date: Date) => {
    const today = new Date();
    return (
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
    );
  };

  const isSelected = (date: Date) => {
    if (!selectedDate) return false;
    return (
      date.getDate() === selectedDate.getDate() &&
      date.getMonth() === selectedDate.getMonth() &&
      date.getFullYear() === selectedDate.getFullYear()
    );
  };

  const weekdays = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

  const displayLabel = selectedDate
    ? selectedDate.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : placeholder;

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((s) => !s)}
        className={cn(
          "w-full h-9 px-3 bg-background border rounded-md text-sm flex items-center justify-between gap-2 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer",
          open
            ? "border-foreground/30 ring-1 ring-foreground/10"
            : "border-border hover:border-foreground/20",
          !selectedDate && "text-muted-foreground"
        )}
      >
        <div className="flex items-center gap-2 truncate">
          <CalendarIcon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{displayLabel}</span>
        </div>
        {selectedDate && !disabled ? (
          <button
            type="button"
            onClick={clearDate}
            className="p-0.5 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground shrink-0 cursor-pointer"
            aria-label="Clear date"
          >
            <X className="size-3.5" />
          </button>
        ) : null}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.12 }}
            className="absolute z-30 mt-1.5 right-0 sm:left-0 w-[280px] rounded-xl border border-border bg-card shadow-xl p-3 select-none"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
              <button
                type="button"
                onClick={prevMonth}
                className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <ChevronLeft className="size-4" />
              </button>
              <span className="text-xs font-semibold text-foreground">
                {monthYearLabel}
              </span>
              <button
                type="button"
                onClick={nextMonth}
                className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>

            {/* Weekdays */}
            <div className="grid grid-cols-7 gap-y-1 text-center mb-1">
              {weekdays.map((wd) => (
                <span key={wd} className="text-[10px] font-bold text-muted-foreground uppercase">
                  {wd}
                </span>
              ))}
            </div>

            {/* Days Grid */}
            <div className="grid grid-cols-7 gap-y-0.5 text-center">
              {daysGrid.map(({ date, currentMonth: isCurr, key }) => {
                const isSel = isSelected(date);
                const isTdy = isToday(date);

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => selectDay(date)}
                    className={cn(
                      "size-8 rounded-lg text-xs font-medium flex items-center justify-center transition-all cursor-pointer relative",
                      !isCurr && "text-muted-foreground/40 hover:text-muted-foreground/70",
                      isCurr && "text-foreground",
                      isCurr && !isSel && !isTdy && "hover:bg-muted",
                      isTdy && !isSel && "border border-foreground/30 font-bold",
                      isSel && "bg-foreground text-background font-bold shadow-sm"
                    )}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
