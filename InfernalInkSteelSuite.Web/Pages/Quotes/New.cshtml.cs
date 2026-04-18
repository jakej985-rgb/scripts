using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.AspNetCore.Mvc.Rendering;
using static InfernalInkSteelSuite.Web.Services.ApiClient;

namespace InfernalInkSteelSuite.Web.Pages.Quotes;

public class NewModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    [BindProperty(SupportsGet = true)]
    public bool IsPopup { get; set; }

    [BindProperty]
    public QuoteInput Quote { get; set; } = new();

    public QuoteEstimate? Estimate { get; set; }

    // Dropdowns
    public List<SelectListItem> Clients { get; set; } = [];
    public List<SelectListItem> Artists { get; set; } = []; // Mock or fetch

    // Style options (simplified)
    public List<SelectListItem> Styles { get; set; } =
    [
        new("Traditional", "Traditional"),
        new("Realism", "Realism"),
        new("Tribal", "Tribal"),
        new("Watercolor", "Watercolor"),
        new("Script", "Script"),
        new("Japanese", "Japanese"),
        new("Fine Line", "Fine Line")
    ];

    public async Task<IActionResult> OnGetAsync(int? clientId)
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
            return RedirectToPage("/Account/Login");

        await LoadDropdowns();

        if (clientId.HasValue)
        {
            Quote.ClientId = clientId;
        }

        // Default complexity
        Quote.CoverageLevel = 1;
        Quote.LineComplexity = 1;
        Quote.ShadingComplexity = 1;
        Quote.ColorComplexity = 1;
        Quote.Difficulty = 1;

        return Page();
    }

    public async Task<IActionResult> OnPostCalculateAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token)) return RedirectToPage("/Account/Login");

        // Simply preview
        Estimate = await _api.CalculateQuoteAsync(Quote);
        await LoadDropdowns();
        return Page();
    }

    public async Task<IActionResult> OnPostSaveAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token)) return RedirectToPage("/Account/Login");

        if (!ModelState.IsValid)
        {
            await LoadDropdowns();
            return Page();
        }

        var result = await _api.CreateQuoteAsync(Quote);
        if (result != null)
        {
            if (IsPopup)
            {
                // Close the window directly
                return Content("<script>window.close();</script>", "text/html");
            }
            return RedirectToPage("/Quotes/Index");
        }

        ModelState.AddModelError(string.Empty, "Failed to create quote.");
        await LoadDropdowns();
        return Page();
    }

    private async Task LoadDropdowns()
    {
        var clients = await _api.GetClientsAsync();
        Clients = [.. clients.Select(c => new SelectListItem(c.FullName, c.Id.ToString()))];

        Artists = [
            new("Jake", "1"),
            new("Guest", "2")
        ];
    }
}
