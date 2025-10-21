

The PayShift gamification system is designed to incentivize high-quality participation on the platform for both workers and employers. It includes:

- Achievement tracking
- Badge awards
- Points and level progression
- Leaderboards 
- Real-time notifications

## Core Components

### Models

- `Achievement`: Represents milestones users can unlock (e.g., completing 10 jobs)
- `Badge`: Represents special recognition for users (e.g., maintaining a high rating)
- `UserAchievement`: Tracks which achievements a user has unlocked
- `UserBadge`: Tracks which badges a user has earned
- `UserPoints`: Tracks a user's points and level progression

### Achievement Types

- `job_count`: Based on number of completed jobs
- `earnings`: Based on total earnings
- `rating`: Based on average user rating
- `referrals`: Based on referred users
- `streak`: Based on consecutive activity (days/jobs)
- `community`: Based on community contributions

### Badge Types

For Workers:
- `job_completion`: Based on job completion metrics
- `rating`: Based on rating metrics
- `streak`: Based on consistency
- `referral`: Based on referrals
- `premium`: For premium users
- `review`: For contributing reviews
- `safety`: For safety compliance
- `community`: For community contribution

For Employers:
- `client_jobs`: Based on job posting metrics
- `client_pay`: Based on fair payment practices
- `client_payment_speed`: Based on payment timing
- `client_rating`: Based on ratings from workers
- `client_diversity`: Based on job category diversity
- `client_community`: For posting jobs in underserved regions

## API Endpoints

### User Progress

- `GET /gamification/progress/{user_id}`: Get user's achievements, badges, and points
- `GET /gamification/mobile-dashboard/{user_id}`: Get mobile-friendly dashboard

### Achievement and Badge Management

- `POST /gamification/check-achievements`: Check and update user achievements
- `POST /gamification/check-badges`: Check and update user badges

### Leaderboards

- `GET /gamification/leaderboards`: Get leaderboards with filtering options

### Admin Endpoints

Admin gamification endpoints are in `admin/api.py` and include:
- CRUD operations for achievements and badges
- User progress management
- Reset functionality

## Integration Points

The gamification system integrates with:
1. Job completion flow
2. Rating system
3. Premium subscription system
4. WebSocket notifications

## WebSockets

Real-time notifications are sent via WebSockets when:
- Achievements are unlocked
- Badges are earned
- Users level up

Connect to `/ws/gamification/` to receive these notifications.

## Testing

The system includes:
- Unit tests for achievement/badge criteria
- Integration tests for job completion flow
- Performance tests with caching

## Performance Considerations

- Database queries are optimized with proper indexing
- Achievement and badge checks are cached
- Batch processing is used for high-volume operations

## Extending the System

To add new achievement or badge types:
1. Add the type to the appropriate model's choices
2. Implement a checker method in `AchievementChecker` or `BadgeChecker`
3. Create achievement/badge instances through the admin interface

## Nigeria-Specific Context

The system includes culturally relevant achievements and badges specific to Nigeria, including:
- State-based achievements
- Local holiday work recognition
- Cross-state work opportunities 