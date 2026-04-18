using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.AspNetCore.Mvc.Rendering;

namespace InfernalInkSteelSuite.Web.Pages.Appointments;

public class EditModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    [BindProperty]
    public AppointmentDto Appointment { get; set; } = new();

    // For dropdowns
    public List<SelectListItem> Clients { get; set; } = [];
    public List<SelectListItem> Artists { get; set; } = []; // Hardcoded for now if no API

    // Services types hardcoded for now or fetch if API exists
    public List<SelectListItem> ServiceTypes { get; set; } =
    [
        new("Tattoo", "Tattoo"),
        new("Piercing", "Piercing"),
        new("Consultation", "Consultation"),
        new("Touch-up", "Touch-up")
    ];

    public string Title { get; set; } = "New Appointment";
    public string? ErrorMessage { get; set; }

    [BindProperty]
    public bool IsPopup { get; set; }

    public async Task<IActionResult> OnGetAsync(int? id)
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
            return RedirectToPage("/Account/Login");

        if (bool.TryParse(Request.Query["isPopup"], out var isPopup)) IsPopup = isPopup;

        await LoadDropdowns();

        if (id.HasValue && id.Value > 0)
        {
            var existing = await _api.GetAppointmentAsync(id.Value);
            if (existing != null)
            {
                Appointment = existing;
                Title = "Edit Appointment";
            }
            else
            {
                return RedirectToPage("/Appointments/Index");
            }
        }
        else
        {
            // Defaults
            Appointment.StartTime = DateTime.Today.AddHours(12); // Noon
            Appointment.EndTime = DateTime.Today.AddHours(13);
        }

        return Page();
    }

    public async Task<IActionResult> OnPostAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
            return RedirectToPage("/Account/Login");

        if (!ModelState.IsValid)
        {
            await LoadDropdowns();
            return Page();
        }

        try
        {
            if (Appointment.Id > 0)
            {
                await _api.UpdateAppointmentAsync(Appointment);
            }
            else
            {
                await _api.CreateAppointmentAsync(Appointment);
            }

            if (IsPopup)
            {
                // Refresh parent if opener exists, then close
                string script = $"<script>if(window.opener) {{ window.opener.refreshAppointmentDetails({Appointment.Id}); }} window.close();</script>";
                return Content(script, "text/html");
            }
        }
        catch (ApiException ex)
        {
            ErrorMessage = ex.Content;
            ModelState.AddModelError("", $"API Error: {ex.Content}");
            await LoadDropdowns();
            return Page();
        }
        catch (Exception ex)
        {
            ErrorMessage = "An unexpected error occurred.";
            ModelState.AddModelError("", $"Error: {ex.Message}");
            await LoadDropdowns();
            return Page();
        }

        return RedirectToPage("/Appointments/Index");
    }

    private async Task LoadDropdowns()
    {
        var clients = await _api.GetClientsAsync();
        Clients = [.. clients.Select(c => new SelectListItem(c.FullName, c.Id.ToString()))];

        // If we don't have GetArtists, we can mock or use a known list for now.
        // Assuming we might need to add GetArtistsAsync to ApiClient too.
        // For MVP, I'll hardcode or valid artist IDs if known.
        // Let's assume we can at least get a list of users or artists? 
        // Step 15 showed no GetArtists. 
        // I'll add a mock list or a basic one.
        Artists = [
            new("Jake (Artist)", "1"),
            new("Guest Artist", "2")
        ];
    }
}
