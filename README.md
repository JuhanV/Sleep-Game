# Sleep Game

A web application that connects to the Oura Ring API to track and compare sleep data with other users, creating a gamified experience for improving sleep habits.

## Features

- OAuth2 integration with Oura Ring API
- Detailed visualization of sleep metrics
- Readiness and activity data tracking
- User comparison through a global leaderboard

## Getting Started

### Prerequisites

- Python 3.8+
- Oura Ring account and API access
- Supabase account for database storage

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd sleep-game
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
```
Edit `.env` with your Oura API credentials and Supabase details.

4. Run the application:
```bash
python src/app.py
```

The application will be available at `http://localhost:5000`.

## How It Works

Sleep Game connects to your Oura Ring data via the Oura API v2 and displays:

- Detailed sleep metrics including sleep stages, heart rate, and HRV data
- Readiness scores with contributing factors
- Activity data including steps and activity scores
- A global leaderboard to compare your sleep performance with others

## License

This project is licensed under the MIT License.

## Acknowledgments

- Oura Ring API for providing the sleep and health data
- Supabase for database functionality 