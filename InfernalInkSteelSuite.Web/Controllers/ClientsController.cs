using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers
{
    public class ClientsController(ApiClient api) : Controller
    {
        private readonly ApiClient _api = api;

        public async Task<IActionResult> Index()
        {
            var clients = await _api.GetClientsAsync()
                          ?? [];
            return View(clients);
        }
    }
}
