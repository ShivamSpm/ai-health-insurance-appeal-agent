"use client";

import { PlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, type NewCase } from "@/lib/api";

const PLANS = [
  { value: "ppo", label: "Halcyon Ridge Silver PPO" },
  { value: "hmo", label: "Halcyon Ridge Bronze HMO" },
  { value: "epo", label: "Halcyon Ridge Gold EPO" },
] as const;

type PlanId = NewCase["plan_id"];

function FileText({ id, onLoad }: { id: string; onLoad: (text: string) => void }) {
  return (
    <input
      id={id}
      type="file"
      accept=".md,.txt,text/plain,text/markdown"
      className="text-xs text-muted-foreground file:mr-2 file:rounded-md file:border file:bg-background file:px-2 file:py-1 file:text-xs"
      onChange={async (e) => {
        const file = e.target.files?.[0];
        if (file) onLoad(await file.text());
      }}
    />
  );
}

export function NewCaseDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [planId, setPlanId] = useState<PlanId>("ppo");
  const [title, setTitle] = useState("");
  const [letter, setLetter] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const letterTooShort = letter.trim().length < 50;

  async function submit() {
    setSaving(true);
    try {
      const created = await api.createCase({
        plan_id: planId,
        denial_letter: letter,
        member_note: note,
        title: title.trim() || null,
      });
      setOpen(false);
      router.push(`/cases/${created.case_id}`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <PlusIcon />
        New case
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New case</DialogTitle>
          <DialogDescription>
            Paste or upload the denial letter and a short note from the member. The plan document
            comes from the insurer, so pick one of the three plans.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>Plan</Label>
              <Select
                items={PLANS}
                value={planId}
                onValueChange={(v) => v && setPlanId(v as PlanId)}
              >
                <SelectTrigger className="w-full" aria-label="Plan">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PLANS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="case-title">Title (optional)</Label>
              <Input
                id="case-title"
                value={title}
                maxLength={120}
                placeholder="e.g. Knee MRI denial"
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="case-letter">Denial letter</Label>
              <FileText id="case-letter-file" onLoad={setLetter} />
            </div>
            <Textarea
              id="case-letter"
              value={letter}
              onChange={(e) => setLetter(e.target.value)}
              className="h-48 font-mono text-xs"
              placeholder="Paste the denial letter (text or Markdown)."
            />
          </div>
          <div className="grid gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="case-note">Member note</Label>
              <FileText id="case-note-file" onLoad={setNote} />
            </div>
            <Textarea
              id="case-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="h-24 text-sm"
              placeholder="What happened, and which documents the member already has."
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={letterTooShort || saving}>
            {saving ? "Creating..." : "Create case"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
