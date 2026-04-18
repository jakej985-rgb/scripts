using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using static InfernalInkSteelSuite.Web.Services.ApiClient;

namespace InfernalInkSteelSuite.Web.Pages.Documents;

public class IndexModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    public List<DocumentDto> Documents { get; set; } = [];

    public async Task<IActionResult> OnGetAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
            return RedirectToPage("/Account/Login");

        Documents = await _api.GetDocumentsAsync() ?? [];

        return Page();
    }
}
