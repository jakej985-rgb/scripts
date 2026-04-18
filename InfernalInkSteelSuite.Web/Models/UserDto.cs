namespace InfernalInkSteelSuite.Web.Models;

public class UserDto
{
    public int Id { get; set; }
    public string Username { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    public string Role { get; set; } = "Staff"; // Admin, Manager, Staff
    public string Skills { get; set; } = "Both"; // Tattoo, Piercing, Both
    public DateTime CreatedAt { get; set; }
}
