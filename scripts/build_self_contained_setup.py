"""Build a one-file Windows setup bootstrap with embedded release resources."""

from __future__ import annotations

import argparse
import os
import struct
import subprocess
import tempfile
from pathlib import Path


CSHARP_SOURCE = r'''
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Eitaa Bridge Graphical Setup")]
[assembly: AssemblyProduct("Eitaa Bridge")]
[assembly: AssemblyCompany("Eitaa Bridge Project")]
[assembly: AssemblyVersion("0.8.0.4")]
[assembly: AssemblyFileVersion("0.8.0.4")]

internal static class SetupBootstrap
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct OsVersionInfo
    {
        public int Size;
        public int Major;
        public int Minor;
        public int Build;
        public int Platform;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string ServicePack;
    }

    [DllImport("ntdll.dll", CharSet = CharSet.Unicode)]
    private static extern int RtlGetVersion(ref OsVersionInfo version);

    private static readonly string[] ResourceNames = new string[]
    {
        "office_payload.zip",
        "install_office_payload.cmd",
        "check_windows_version.vbs"
    };

    [STAThread]
    private static int Main(string[] args)
    {
        bool verifyOnly = args.Length == 1 && args[0] == "--verify-only";
        if (args.Length != 0 && !verifyOnly)
        {
            ReportError("ورودی ناشناخته‌ای به نصب‌کننده داده شده است.", verifyOnly);
            return 2;
        }

        int compatibility = CheckCompatibility(verifyOnly);
        if (compatibility != 0)
        {
            return compatibility;
        }
        if (verifyOnly)
        {
            return VerifyResources();
        }

        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        using (SetupForm form = new SetupForm())
        {
            Application.Run(form);
            return form.ExitCode;
        }
    }

    private static int CheckCompatibility(bool verifyOnly)
    {
        OsVersionInfo version = new OsVersionInfo();
        version.Size = Marshal.SizeOf(typeof(OsVersionInfo));
        if (RtlGetVersion(ref version) != 0)
        {
            ReportError("سازگاری نسخه ویندوز قابل بررسی نیست.", verifyOnly);
            return 11;
        }
        if (version.Major < 10)
        {
            ReportError("Eitaa Bridge به ویندوز ۱۰ یا ۱۱ نسخه ۶۴ بیتی نیاز دارد.", verifyOnly);
            return 10;
        }
        if (!Environment.Is64BitOperatingSystem)
        {
            ReportError("Eitaa Bridge به ویندوز ۶۴ بیتی نیاز دارد.", verifyOnly);
            return 12;
        }
        return 0;
    }

    private static int VerifyResources()
    {
        Assembly assembly = Assembly.GetExecutingAssembly();
        foreach (string name in ResourceNames)
        {
            using (Stream stream = assembly.GetManifestResourceStream(name))
            {
                if (stream == null || stream.Length == 0)
                {
                    Console.Error.WriteLine("Setup resource is missing or empty: " + name);
                    return 20;
                }
            }
        }
        Console.WriteLine("Eitaa Bridge setup resources verified.");
        return 0;
    }

    internal static InstallResult InstallPayload()
    {
        string staging = Path.Combine(
            Path.GetTempPath(),
            "EitaaBridgeSetup-" + Guid.NewGuid().ToString("N")
        );
        try
        {
            Directory.CreateDirectory(staging);
            Assembly assembly = Assembly.GetExecutingAssembly();
            foreach (string name in ResourceNames)
            {
                string destination = Path.Combine(staging, name);
                using (Stream source = assembly.GetManifestResourceStream(name))
                {
                    if (source == null)
                    {
                        return new InstallResult(20, "یکی از اجزای داخلی نصب‌کننده پیدا نشد.");
                    }
                    using (FileStream target = new FileStream(destination, FileMode.CreateNew, FileAccess.Write))
                    {
                        source.CopyTo(target);
                        target.Flush(true);
                    }
                }
                if (new FileInfo(destination).Length == 0)
                {
                    return new InstallResult(21, "یکی از اجزای داخلی نصب‌کننده خالی است.");
                }
            }

            string command = Environment.GetEnvironmentVariable("ComSpec");
            if (String.IsNullOrWhiteSpace(command))
            {
                command = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "cmd.exe");
            }
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = command;
            start.Arguments = "/d /c \"\"" + Path.Combine(staging, "install_office_payload.cmd") + "\" /quiet\"";
            start.WorkingDirectory = staging;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.WindowStyle = ProcessWindowStyle.Hidden;
            using (Process child = Process.Start(start))
            {
                if (child == null)
                {
                    return new InstallResult(22, "فرایند نصب قابل اجرا نیست.");
                }
                child.WaitForExit();
                if (child.ExitCode != 0)
                {
                    return new InstallResult(child.ExitCode, "نصب کامل نشد. داده‌های نسخه قبلی عمداً حذف نشده‌اند.");
                }
                return new InstallResult(0, "نصب با موفقیت انجام شد.");
            }
        }
        catch (Exception)
        {
            return new InstallResult(30, "نصب‌کننده با یک خطای پیش‌بینی‌نشده متوقف شد.");
        }
        finally
        {
            TryDelete(staging);
        }
    }

    private static void ReportError(string message, bool consoleOnly)
    {
        Console.Error.WriteLine(message);
        if (!consoleOnly)
        {
            MessageBox.Show(message, "نصب Eitaa Bridge", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static void TryDelete(string directory)
    {
        for (int attempt = 0; attempt < 5; attempt++)
        {
            try
            {
                if (Directory.Exists(directory))
                {
                    Directory.Delete(directory, true);
                }
                return;
            }
            catch
            {
                Thread.Sleep(200);
            }
        }
    }
}

internal sealed class InstallResult
{
    internal InstallResult(int exitCode, string message)
    {
        ExitCode = exitCode;
        Message = message;
    }

    internal int ExitCode { get; private set; }
    internal string Message { get; private set; }
}

internal sealed class SetupForm : Form
{
    private readonly Button installButton;
    private readonly Button cancelButton;
    private readonly ProgressBar progress;
    private readonly Label statusLabel;
    private readonly CheckBox launchAfterInstall;
    private readonly System.ComponentModel.BackgroundWorker worker;

    internal SetupForm()
    {
        Text = "نصب Eitaa Bridge";
        ClientSize = new Size(680, 450);
        MinimumSize = new Size(696, 489);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        RightToLeft = RightToLeft.Yes;
        RightToLeftLayout = true;
        Font = new Font("Segoe UI", 9.5F);
        BackColor = Color.White;
        ExitCode = 2;
        try
        {
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        }
        catch
        {
        }

        Panel header = new Panel();
        header.Dock = DockStyle.Top;
        header.Height = 92;
        header.BackColor = Color.FromArgb(15, 147, 209);
        Controls.Add(header);

        PictureBox logo = new PictureBox();
        logo.Location = new Point(598, 14);
        logo.Size = new Size(62, 62);
        logo.SizeMode = PictureBoxSizeMode.Zoom;
        try
        {
            logo.Image = Icon.ToBitmap();
        }
        catch
        {
        }
        header.Controls.Add(logo);

        Label title = new Label();
        title.Text = "نصب نسخه اختصاصی Eitaa Bridge";
        title.Font = new Font("Segoe UI", 15F, FontStyle.Bold);
        title.ForeColor = Color.White;
        title.TextAlign = ContentAlignment.MiddleRight;
        title.Location = new Point(24, 13);
        title.Size = new Size(555, 36);
        header.Controls.Add(title);

        Label subtitle = new Label();
        subtitle.Text = "همراه با فعال‌سازی دستگاهی و تمام نیازمندی‌های لازم";
        subtitle.ForeColor = Color.White;
        subtitle.TextAlign = ContentAlignment.MiddleRight;
        subtitle.Location = new Point(24, 49);
        subtitle.Size = new Size(555, 26);
        header.Controls.Add(subtitle);

        Label intro = new Label();
        intro.Text = "این برنامه در مسیر زیر نصب یا به‌روزرسانی می‌شود:";
        intro.TextAlign = ContentAlignment.MiddleRight;
        intro.Location = new Point(28, 117);
        intro.Size = new Size(624, 25);
        Controls.Add(intro);

        TextBox path = new TextBox();
        path.ReadOnly = true;
        path.RightToLeft = RightToLeft.No;
        path.Text = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            "EitaaBridge"
        );
        path.Location = new Point(28, 148);
        path.Size = new Size(624, 25);
        path.BackColor = Color.FromArgb(245, 248, 251);
        Controls.Add(path);

        Label details = new Label();
        details.Text = "• Python به‌صورت داخلی همراه برنامه است و Node.js روی سیستم مقصد لازم نیست.\r\n"
            + "• میان‌برهای Desktop و Start Menu با آیکون برنامه ساخته می‌شوند.\r\n"
            + "• هنگام به‌روزرسانی، تنظیمات، نشست، داده‌ها، گزارش‌ها و فعال‌سازی قبلی حفظ می‌شوند.";
        details.TextAlign = ContentAlignment.TopRight;
        details.Location = new Point(28, 194);
        details.Size = new Size(624, 84);
        Controls.Add(details);

        launchAfterInstall = new CheckBox();
        launchAfterInstall.Text = "اجرای Eitaa Bridge پس از پایان نصب";
        launchAfterInstall.Checked = true;
        launchAfterInstall.AutoSize = true;
        launchAfterInstall.Location = new Point(393, 293);
        Controls.Add(launchAfterInstall);

        statusLabel = new Label();
        statusLabel.Text = "برای شروع، دکمه «نصب» را انتخاب کنید.";
        statusLabel.TextAlign = ContentAlignment.MiddleRight;
        statusLabel.Location = new Point(28, 326);
        statusLabel.Size = new Size(624, 25);
        Controls.Add(statusLabel);

        progress = new ProgressBar();
        progress.Location = new Point(28, 357);
        progress.Size = new Size(624, 18);
        progress.Style = ProgressBarStyle.Blocks;
        Controls.Add(progress);

        installButton = new Button();
        installButton.Text = "نصب";
        installButton.Location = new Point(544, 397);
        installButton.Size = new Size(108, 34);
        installButton.BackColor = Color.FromArgb(15, 147, 209);
        installButton.ForeColor = Color.White;
        installButton.FlatStyle = FlatStyle.Flat;
        installButton.Click += StartInstall;
        Controls.Add(installButton);

        cancelButton = new Button();
        cancelButton.Text = "انصراف";
        cancelButton.Location = new Point(426, 397);
        cancelButton.Size = new Size(108, 34);
        cancelButton.Click += delegate { Close(); };
        Controls.Add(cancelButton);

        AcceptButton = installButton;
        CancelButton = cancelButton;

        worker = new System.ComponentModel.BackgroundWorker();
        worker.DoWork += delegate(object sender, System.ComponentModel.DoWorkEventArgs args)
        {
            args.Result = SetupBootstrap.InstallPayload();
        };
        worker.RunWorkerCompleted += FinishInstall;
        FormClosing += PreventCloseWhileInstalling;
    }

    internal int ExitCode { get; private set; }

    private void StartInstall(object sender, EventArgs args)
    {
        installButton.Enabled = false;
        cancelButton.Enabled = false;
        launchAfterInstall.Enabled = false;
        progress.Style = ProgressBarStyle.Marquee;
        progress.MarqueeAnimationSpeed = 28;
        statusLabel.Text = "در حال نصب؛ لطفاً چند لحظه صبر کنید...";
        worker.RunWorkerAsync();
    }

    private void FinishInstall(object sender, System.ComponentModel.RunWorkerCompletedEventArgs args)
    {
        progress.Style = ProgressBarStyle.Blocks;
        progress.Value = args.Error == null ? 100 : 0;
        InstallResult result = args.Error == null ? (InstallResult)args.Result : new InstallResult(30, "نصب‌کننده متوقف شد.");
        ExitCode = result.ExitCode;
        if (result.ExitCode != 0)
        {
            statusLabel.Text = result.Message;
            installButton.Enabled = true;
            cancelButton.Enabled = true;
            launchAfterInstall.Enabled = true;
            MessageBox.Show(this, result.Message + "\r\nکد خطا: " + result.ExitCode, "نصب ناموفق", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        statusLabel.Text = result.Message;
        if (launchAfterInstall.Checked)
        {
            try
            {
                string target = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "Programs",
                    "EitaaBridge",
                    "EitaaBridgeOffice.vbs"
                );
                Process.Start(new ProcessStartInfo("wscript.exe", "\"" + target + "\"") { UseShellExecute = true });
            }
            catch
            {
                MessageBox.Show(this, "نصب انجام شد، اما اجرای خودکار برنامه ممکن نشد. از میان‌بر Desktop استفاده کنید.", "نصب Eitaa Bridge", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
        }
        MessageBox.Show(this, "Eitaa Bridge با موفقیت نصب یا به‌روزرسانی شد.", "پایان نصب", MessageBoxButtons.OK, MessageBoxIcon.Information);
        Close();
    }

    private void PreventCloseWhileInstalling(object sender, FormClosingEventArgs args)
    {
        if (worker.IsBusy)
        {
            args.Cancel = true;
        }
    }
}
'''


def locate_compiler() -> Path:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = (
        windows / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe",
        windows / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("The .NET Framework C# compiler was not found.")


def validate_windows_icon(icon: Path) -> Path:
    selected = icon.resolve(strict=True)
    payload = selected.read_bytes()
    if len(payload) < 22:
        raise ValueError("Windows icon is truncated or empty.")
    reserved, image_type, count = struct.unpack_from("<HHH", payload)
    if reserved != 0 or image_type != 1 or count < 1 or count > 256:
        raise ValueError("Windows icon has an invalid ICO header.")
    table_end = 6 + (16 * count)
    if table_end > len(payload):
        raise ValueError("Windows icon directory is truncated.")
    for index in range(count):
        entry_offset = 6 + (16 * index)
        image_size, image_offset = struct.unpack_from("<II", payload, entry_offset + 8)
        if image_size <= 0 or image_offset < table_end or image_offset + image_size > len(payload):
            raise ValueError("Windows icon contains an invalid image entry.")
    return selected


def build_setup(
    *,
    payload: Path,
    installer: Path,
    preflight: Path,
    icon: Path,
    output: Path,
) -> Path:
    resources = {
        "office_payload.zip": payload.resolve(strict=True),
        "install_office_payload.cmd": installer.resolve(strict=True),
        "check_windows_version.vbs": preflight.resolve(strict=True),
    }
    for name, path in resources.items():
        if path.stat().st_size <= 0:
            raise ValueError(f"Setup resource is empty: {name}")
    selected_icon = validate_windows_icon(icon)

    selected_output = output.resolve()
    selected_output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = selected_output.with_name(f".{selected_output.name}.tmp.exe")
    if temporary_output.exists():
        raise FileExistsError("Temporary setup output already exists; review is required.")

    with tempfile.TemporaryDirectory(prefix="eitaa-setup-csharp-") as temporary:
        source = Path(temporary) / "SetupBootstrap.cs"
        source.write_text(CSHARP_SOURCE, encoding="utf-8-sig")
        command = [
            str(locate_compiler()),
            "/nologo",
            "/target:winexe",
            "/platform:anycpu",
            "/optimize+",
            "/reference:System.Drawing.dll",
            "/reference:System.Windows.Forms.dll",
            f"/win32icon:{selected_icon}",
            f"/out:{temporary_output}",
            *(f"/resource:{path},{name}" for name, path in resources.items()),
            str(source),
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0 or not temporary_output.is_file():
            temporary_output.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "compiler failed").strip()
            raise RuntimeError(detail)
    temporary_output.replace(selected_output)
    return selected_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--icon", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = build_setup(
        payload=args.payload,
        installer=args.installer,
        preflight=args.preflight,
        icon=args.icon,
        output=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
