using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Infrastructure.Abstract;
using FinancialIQ.Api.Infrastructure.EntityFramework;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

builder.Services.AddDbContext<FinancialIqDbContext >(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("FinancialIqDb")));

// CQRS-lite: write side (command) and read side (query) are registered separately
builder.Services.AddScoped<IFinancialIqResultDal, EfFinancialIqResultDal>();
builder.Services.AddScoped<IFinancialIqCommandService, FinancialIqCommandManager>();
builder.Services.AddScoped<IFinancialIqReadDal, EfFinancialIqReadDal>();
builder.Services.AddScoped<IFinancialIqQueryService, FinancialIqQueryManager>();

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseAuthorization();
app.MapControllers();
app.Run();