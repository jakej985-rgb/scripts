using InfernalInkSteelSuite.Data;
using InfernalInkSteelSuite.Repositories;
using InfernalInkSteelSuite.Web.Models;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers;

[ApiController]
[Route("api/[controller]")]
public class UsersController(IUserRepository userRepository) : ControllerBase
{
    private readonly IUserRepository _userRepository = userRepository;

    [HttpGet]
    public IActionResult GetAll()
    {
        var users = _userRepository.GetAllUsers();
        var dtos = users.Select(u => new UserDto
        {
            Id = u.Id,
            Username = u.Username,
            DisplayName = u.DisplayName,
            Role = u.Role ?? string.Empty,
            Skills = "Both",
            CreatedAt = u.CreatedAt
        });

        return Ok(dtos);
    }
}
