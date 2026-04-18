using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers;

public class DocumentsController(ApiClient api) : Controller
{
    private readonly ApiClient _api = api;

    public async Task<IActionResult> Index(int? clientId)
    {
        if (clientId.HasValue)
        {
            var docs = await _api.GetDocumentsForClientAsync(clientId.Value);
            ViewData["ClientId"] = clientId;
            return View(docs);
        }
        else
        {
            // If no client selected, maybe show empty or list all (if API supported listing all)
            // For now, empty list or redirect to Clients
            return View(new List<ApiClient.DocumentDto>());
        }
    }

    [HttpPost]
    public async Task<IActionResult> Upload(int clientId, string title, IFormFile file)
    {
        // Get current user ID from session/claims (assuming "UserId" in session from Login)
        var userId = HttpContext.Session.GetInt32("UserId") ?? 0;

        if (userId == 0) return RedirectToAction("Login", "Account");

        await _api.UploadDocumentAsync(clientId, userId, title, file);
        return RedirectToAction("Index", new { clientId });
    }
}
