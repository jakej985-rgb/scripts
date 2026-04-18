using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace InfernalInkSteelSuite.Web.Pages.Account;

public class LogoutModel : PageModel
{
    public IActionResult OnGet()
    {
        HttpContext.Session.Clear();
        return RedirectToPage("/Account/Login");
    }

    public IActionResult OnPost()
    {
        HttpContext.Session.Clear();
        return RedirectToPage("/Account/Login");
    }
}
