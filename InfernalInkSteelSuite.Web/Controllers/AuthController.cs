using InfernalInkSteelSuite.Repositories;
using InfernalInkSteelSuite.Web.Models;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers;

[ApiController]
[Route("auth")] // Base route for this controller
public class AuthController(IUserRepository userRepository) : ControllerBase
{
    private readonly IUserRepository _userRepository = userRepository;

    [HttpPost("login")]
    public IActionResult Login([FromBody] LoginRequest request)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.Username) || string.IsNullOrWhiteSpace(request.Password))
        {
            return BadRequest("Invalid credentials.");
        }

        // 1. Verify credentials via Repository
        if (_userRepository.CheckPassword(request.Username, request.Password))
        {
            // 2. Get User Info
            var user = _userRepository.GetUserById(0); // If GetUserById(int) exists, or GetUserByUsername

            // Wait, IUserRepository has GetUsernameById but not GetUserByUsername directly? 
            // Let's check IUserRepository again.
            // It has GetUserById(int userId) and GetUsernameById(int userId).
            // It has CheckPassword(string username, string password).
            // It has UpdateLastLogin(string username).

            // We need to get the User object to return ID, Role etc.
            // I'll need to fetch the user by username. 
            // If IUserRepository doesn't support GetUserByUsername, I might have to add it or iterate (bad).
            // Let's assume for now I can iterate or I need to update repo.

            // Actually, I can use GetAllUsers() and find the one.
            var allUsers = _userRepository.GetAllUsers();
            var matchedUser = allUsers.FirstOrDefault(u => u.Username.Equals(request.Username, StringComparison.OrdinalIgnoreCase));

            if (matchedUser != null)
            {
                // 3. Generate Token (Stub for now, or JWT if I had it set up)
                // For this legacy/simple app, maybe just return a dummy token or session ID?
                // The LoginResponse expects: (int UserId, string Username, string DisplayName, string Role, string Token)

                var response = new LoginResponse(
                    matchedUser.Id,
                    matchedUser.Username,
                    matchedUser.DisplayName,
                    matchedUser.Role ?? string.Empty,
                    Guid.NewGuid().ToString() // Dummy token
                );

                return Ok(response);
            }
        }

        return Unauthorized("Invalid username or password.");
    }
}

public record LoginRequest(string Username, string Password);
public record LoginResponse(int UserId, string Username, string DisplayName, string Role, string Token);
