# God Mode Documentation

## Overview

God Mode is an administrative interface that provides advanced monitoring, control, and management capabilities for the Payshift application. It allows administrators to:

- Monitor user activity and system performance
- Manage users and their data
- View and process payment webhooks
- Synchronize Redis cache with the database
- Export data in various formats
- Run simulations and view metrics
- View user rankings and leaderboards

## Features

### User Management

- View user activity logs
- Delete users and admins
- View user profiles and details
- Verify user locations

### Payment Webhook Management

- View webhook logs with filtering options
- Reprocess failed webhooks
- View webhook statistics
- Capture payment webhooks with unique IDs

### Cache Synchronization

- Synchronize Redis cache with the database
- View cache statistics
- Force synchronization when needed
- Sync specific models or all models

### Data Export

- Export data in various formats (CSV, XLSX, JSON)
- Create and manage export configurations
- Customize columns and filters
- View export history

### Simulations

- Run various types of simulations
- View simulation results and metrics
- Monitor simulation performance

### User Rankings

- View user rankings based on various metrics
- Generate and update rankings
- View leaderboards

### Security Dashboard

- Monitor security-related activities
- View failed login attempts
- View admin actions
- Monitor payment processing

## API Endpoints

### User Management

- `POST /godmode/api/users/delete`: Delete a user account

### Payment Webhook Management

- `GET /godmode/api/webhooks`: List payment webhooks with filtering options
- `GET /godmode/api/webhooks/{webhook_id}`: Get details of a specific webhook
- `POST /godmode/api/webhooks/reprocess`: Reprocess a failed webhook
- `GET /godmode/api/webhooks/stats`: Get statistics about webhooks

### Cache Synchronization

- `POST /godmode/api/cache/sync`: Synchronize Redis cache with the database
- `GET /godmode/api/cache/stats`: Get Redis cache statistics

### Data Export

- `GET /godmode/api/exports/configs`: List data export configurations
- `POST /godmode/api/exports/configs`: Create a new data export configuration
- `POST /godmode/api/exports/run`: Run a data export using a configuration
- `GET /godmode/api/exports/models`: List models available for export

### User Rankings

- `GET /godmode/api/rankings`: Get user rankings for a specific type
- `POST /godmode/api/rankings/generate`: Generate or update user rankings

### Simulations

- `POST /godmode/api/simulations/run`: Run a simulation
- `GET /godmode/api/simulations/{simulation_id}`: Get details of a specific simulation
- `GET /godmode/api/simulations`: List simulations with filtering options

### Dashboard

- `GET /godmode/api/dashboard/stats`: Get statistics for the God Mode dashboard

## Models

### SimulationRun

Tracks simulation runs initiated from the God Mode interface.

- `simulation_type`: Type of simulation (admin, client, applicant, job, application, payment, dispute, location, webhook, full)
- `parameters`: JSON field with simulation parameters
- `status`: Status of the simulation (pending, running, completed, failed)
- `result`: JSON field with simulation results
- `started_at`: Timestamp when the simulation started
- `completed_at`: Timestamp when the simulation completed
- `initiated_by`: User who initiated the simulation

### UserActivityLog

Tracks detailed user activity for God Mode monitoring.

- `user`: User who performed the action
- `action_type`: Type of action (login, logout, view_profile, update_profile, view_job, create_job, apply_job, payment, message, location_update, dispute, admin_action, simulation, other)
- `timestamp`: Timestamp when the action occurred
- `ip_address`: IP address of the user
- `user_agent`: User agent of the user
- `details`: JSON field with additional details

### LocationVerification

Stores location verification results for comparing claimed addresses with location history.

- `user`: User being verified
- `claimed_address`: Address claimed by the user
- `claimed_latitude`: Latitude of the claimed address
- `claimed_longitude`: Longitude of the claimed address
- `actual_locations`: JSON field with location history points
- `verification_status`: Status of the verification (pending, verified, suspicious, invalid)
- `verification_details`: JSON field with verification details
- `created_at`: Timestamp when the verification was created
- `verified_at`: Timestamp when the verification was completed
- `verified_by`: User who performed the verification

### WebhookLog

Stores logs of payment webhook calls for monitoring and debugging.

- `reference`: Payment reference
- `gateway`: Payment gateway (paystack, flutterwave, other)
- `status`: Status of the webhook (success, failed, pending, error)
- `request_data`: JSON field with request data
- `response_data`: JSON field with response data
- `error_message`: Error message if any
- `ip_address`: IP address of the webhook sender
- `created_at`: Timestamp when the webhook was received

### WorkAssignment

Tracks work assignments for admin staff.

- `admin`: Admin assigned to the task
- `assigned_by`: User who assigned the task
- `title`: Title of the task
- `description`: Description of the task
- `task_type`: Type of task (dispute, verification, payment, support, other)
- `priority`: Priority of the task (low, medium, high, urgent)
- `status`: Status of the task (pending, in_progress, completed, cancelled)
- `related_object_type`: Type of related object
- `related_object_id`: ID of related object
- `due_date`: Due date for the task
- `created_at`: Timestamp when the task was created
- `updated_at`: Timestamp when the task was last updated
- `completed_at`: Timestamp when the task was completed
- `notes`: Additional notes

### DataExportConfig

Stores configurations for data exports.

- `name`: Name of the configuration
- `description`: Description of the configuration
- `model_name`: Name of the model to export
- `fields`: JSON field with fields to export
- `filters`: JSON field with filters to apply
- `created_by`: User who created the configuration
- `created_at`: Timestamp when the configuration was created
- `last_used`: Timestamp when the configuration was last used

### DataExport

Tracks data exports.

- `config`: Export configuration used
- `file_name`: Name of the exported file
- `file_path`: Path to the exported file
- `status`: Status of the export (pending, processing, completed, failed)
- `row_count`: Number of rows exported
- `created_by`: User who initiated the export
- `created_at`: Timestamp when the export was initiated
- `completed_at`: Timestamp when the export was completed
- `error_message`: Error message if any

### UserRanking

Stores user rankings based on various metrics.

- `user`: User being ranked
- `ranking_type`: Type of ranking (points, payments, jobs_created, jobs_completed, applications, activity)
- `rank`: Rank of the user
- `score`: Score of the user
- `percentile`: Percentile of the user
- `previous_rank`: Previous rank of the user
- `previous_score`: Previous score of the user
- `updated_at`: Timestamp when the ranking was last updated

## Security Considerations

### Authentication and Authorization

- All God Mode features require authentication
- Most features require superuser privileges
- User deletion and other sensitive operations require additional confirmation

### Data Protection

- Sensitive data is properly sanitized before display
- Export functionality includes proper data protection measures
- Webhook logs sanitize sensitive payment information

### Audit Logging

- All administrative actions are logged
- User deletions include detailed audit logs
- Cache synchronization operations are logged

## Performance Considerations

### Cache Synchronization

- Cache synchronization is designed to minimize database load
- Timestamps are used to ensure only newer data is synchronized
- Batch processing is used for large datasets

### Data Export

- Data exports use pagination for large datasets
- Export configurations can be saved for reuse
- Export operations are tracked and can be monitored

### Webhook Processing

- Webhook processing is designed to be fast and reliable
- Failed webhooks can be reprocessed
- Webhook statistics provide insights into performance

## Best Practices

### Cache Management

1. **Regular Synchronization**: Regularly synchronize cache with the database to ensure data consistency
2. **Monitoring**: Monitor cache hit rates and memory usage
3. **Selective Synchronization**: Use selective synchronization for specific models when needed
4. **Force with Caution**: Use force synchronization with caution as it can overwrite newer database data

### Data Export

1. **Reusable Configurations**: Create reusable export configurations for common export tasks
2. **Filtering**: Use appropriate filters to limit the amount of data exported
3. **Field Selection**: Select only the necessary fields to export
4. **Format Selection**: Choose the appropriate format based on the data and use case

### Webhook Management

1. **Regular Monitoring**: Regularly monitor webhook logs for failures
2. **Reprocessing**: Reprocess failed webhooks promptly
3. **Error Analysis**: Analyze webhook errors to identify patterns and issues

### User Management

1. **Verification**: Verify user locations and activities regularly
2. **Deletion Caution**: Use user deletion with caution as it cannot be undone
3. **Activity Monitoring**: Monitor user activity for suspicious behavior

## Troubleshooting

### Cache Synchronization Issues

- **Missing Timestamps**: If timestamps are missing, force synchronization may be necessary
- **Sync Failures**: Check the sync log for specific error messages
- **Redis Connection**: Ensure Redis is running and accessible

### Webhook Processing Issues

- **Gateway Errors**: Check the webhook error message for gateway-specific issues
- **Reference Mismatch**: Ensure the payment reference matches the webhook reference
- **Authentication**: Verify that the gateway API keys are correct

### Data Export Issues

- **Export Failures**: Check the export error message for specific issues
- **Large Datasets**: For large datasets, use appropriate filters to limit the data
- **Format Issues**: If format issues occur, try a different export format

## Conclusion

God Mode provides powerful tools for managing and monitoring the Payshift application. By following the best practices and understanding the features, administrators can effectively manage the system and ensure its smooth operation.
