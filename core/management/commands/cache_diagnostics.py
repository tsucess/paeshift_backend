"""
Management command for cache diagnostics.

This command provides comprehensive diagnostics for the cache system,
including consistency checks, performance metrics, and issue detection.
"""

import json
import logging
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.cache_telemetry import get_cache_telemetry
from godmode.cache_sync import check_cache_consistency, reconcile_cache_for_model
from core.cache_warming import get_cacheable_models

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run diagnostics on the cache system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Model to diagnose (app_label.model_name)',
        )
        parser.add_argument(
            '--check-consistency',
            action='store_true',
            help='Check cache consistency',
        )
        parser.add_argument(
            '--check-performance',
            action='store_true',
            help='Check cache performance',
        )
        parser.add_argument(
            '--check-issues',
            action='store_true',
            help='Check for cache issues',
        )
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Fix detected issues',
        )
        parser.add_argument(
            '--sample-size',
            type=int,
            default=100,
            help='Number of instances to check for consistency',
        )
        parser.add_argument(
            '--time-range',
            type=int,
            default=24,
            help='Time range in hours for performance metrics',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
        parser.add_argument(
            '--output',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format',
        )

    def handle(self, *args, **options):
        model_name = options.get('model')
        check_consistency = options.get('check_consistency', False)
        check_performance = options.get('check_performance', False)
        check_issues = options.get('check_issues', False)
        fix_issues = options.get('fix_issues', False)
        sample_size = options.get('sample_size', 100)
        time_range = options.get('time_range', 24)
        verbose = options.get('verbose', False)
        output_format = options.get('output', 'text')
        
        # If no specific checks are requested, run all checks
        if not any([check_consistency, check_performance, check_issues]):
            check_consistency = True
            check_performance = True
            check_issues = True
        
        # Set up logging
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        
        # Get models to check
        models = []
        if model_name:
            # Get specific model
            try:
                from django.apps import apps
                app_label, model_name = model_name.split('.')
                model = apps.get_model(app_label, model_name)
                models = [model]
            except ValueError:
                raise CommandError(f"Invalid model name: {model_name}. Use format 'app_label.model_name'")
            except LookupError:
                raise CommandError(f"Model not found: {model_name}")
        else:
            # Get all cacheable models
            models = get_cacheable_models()
        
        # Initialize results
        results = {
            'timestamp': timezone.now().isoformat(),
            'models_checked': len(models),
            'consistency': {},
            'performance': {},
            'issues': {},
            'fixes': {},
        }
        
        # Check consistency
        if check_consistency:
            self.stdout.write("Checking cache consistency...")
            
            for model in models:
                model_label = f"{model._meta.app_label}.{model.__name__}"
                self.stdout.write(f"  Checking {model_label}...")
                
                # Check consistency
                stats = check_cache_consistency(model, sample_size=sample_size)
                
                # Calculate consistency ratio
                total = stats['total']
                if total > 0:
                    consistency_ratio = stats['consistent'] / total
                else:
                    consistency_ratio = 1.0
                
                # Add to results
                results['consistency'][model_label] = {
                    'total': stats['total'],
                    'consistent': stats['consistent'],
                    'inconsistent': stats['inconsistent'],
                    'missing': stats['missing'],
                    'consistency_ratio': consistency_ratio,
                    'inconsistent_fields': stats['inconsistent_fields'],
                }
                
                # Output results
                if output_format == 'text':
                    self.stdout.write(f"    Total: {stats['total']}")
                    self.stdout.write(f"    Consistent: {stats['consistent']} ({consistency_ratio:.2%})")
                    self.stdout.write(f"    Inconsistent: {stats['inconsistent']} ({stats['inconsistent'] / total if total > 0 else 0:.2%})")
                    self.stdout.write(f"    Missing: {stats['missing']} ({stats['missing'] / total if total > 0 else 0:.2%})")
                    
                    if stats['inconsistent_fields']:
                        self.stdout.write("    Inconsistent fields:")
                        for field, count in stats['inconsistent_fields'].items():
                            self.stdout.write(f"      {field}: {count} instances")
                    
                    if verbose and stats['details']:
                        self.stdout.write("    Details:")
                        for detail in stats['details']:
                            if detail['status'] != 'consistent':
                                self.stdout.write(f"      {detail['id']}: {detail['message']}")
        
        # Check performance
        if check_performance:
            self.stdout.write("Checking cache performance...")
            
            # Get time range
            end_time = timezone.now()
            start_time = end_time - timedelta(hours=time_range)
            
            for model in models:
                model_label = f"{model._meta.app_label}.{model.__name__}"
                self.stdout.write(f"  Checking {model_label}...")
                
                # Get telemetry
                telemetry = get_cache_telemetry(model.__name__.lower(), start_time, end_time)
                
                # Calculate metrics
                hit_rate = 0
                latency = 0
                error_rate = 0
                
                # Hit rate
                hit_rates = []
                for model_name, intervals in telemetry.get('hit_rate', {}).items():
                    for interval, data in intervals.items():
                        hit_rates.append(data.get('rate', 0))
                
                if hit_rates:
                    hit_rate = sum(hit_rates) / len(hit_rates)
                
                # Latency
                latencies = []
                for model_name, operations in telemetry.get('latency', {}).items():
                    for operation, intervals in operations.items():
                        for interval, data in intervals.items():
                            latencies.append(data.get('avg', 0))
                
                if latencies:
                    latency = sum(latencies) / len(latencies)
                
                # Error rate
                errors = 0
                operations = 0
                for model_name, intervals in telemetry.get('operations', {}).items():
                    for interval, data in intervals.items():
                        errors += data.get('error', 0)
                        operations += data.get('count', 0)
                
                if operations > 0:
                    error_rate = errors / operations
                
                # Add to results
                results['performance'][model_label] = {
                    'hit_rate': hit_rate,
                    'latency': latency,
                    'error_rate': error_rate,
                    'operations': operations,
                    'errors': errors,
                }
                
                # Output results
                if output_format == 'text':
                    self.stdout.write(f"    Hit rate: {hit_rate:.2%}")
                    self.stdout.write(f"    Average latency: {latency:.2f}ms")
                    self.stdout.write(f"    Error rate: {error_rate:.2%}")
                    self.stdout.write(f"    Total operations: {operations}")
                    self.stdout.write(f"    Total errors: {errors}")
        
        # Check for issues
        if check_issues:
            self.stdout.write("Checking for cache issues...")
            
            for model in models:
                model_label = f"{model._meta.app_label}.{model.__name__}"
                self.stdout.write(f"  Checking {model_label}...")
                
                # Initialize issues
                issues = []
                
                # Check for timestamp fields
                has_timestamp = False
                for field_name in ['last_updated', 'updated_at', 'timestamp', 'modified_at']:
                    if hasattr(model, field_name):
                        has_timestamp = True
                        break
                
                if not has_timestamp:
                    issues.append({
                        'type': 'missing_timestamp',
                        'message': f"Model {model_label} is missing a standard timestamp field",
                        'severity': 'high',
                        'fix': "Add a 'last_updated' field with auto_now=True",
                    })
                
                # Check for version field
                has_version = hasattr(model, 'version')
                if not has_version:
                    issues.append({
                        'type': 'missing_version',
                        'message': f"Model {model_label} is missing a version field",
                        'severity': 'medium',
                        'fix': "Add a 'version' field that increments on each save",
                    })
                
                # Check for cache consistency issues
                if check_consistency and model_label in results['consistency']:
                    consistency = results['consistency'][model_label]
                    if consistency['consistency_ratio'] < 0.9:
                        issues.append({
                            'type': 'low_consistency',
                            'message': f"Model {model_label} has low cache consistency ({consistency['consistency_ratio']:.2%})",
                            'severity': 'high',
                            'fix': "Run 'python manage.py reconcile_cache --model {model_label}'",
                            'details': {
                                'consistency_ratio': consistency['consistency_ratio'],
                                'inconsistent_fields': consistency['inconsistent_fields'],
                            },
                        })
                
                # Check for performance issues
                if check_performance and model_label in results['performance']:
                    performance = results['performance'][model_label]
                    if performance['hit_rate'] < 0.8:
                        issues.append({
                            'type': 'low_hit_rate',
                            'message': f"Model {model_label} has low cache hit rate ({performance['hit_rate']:.2%})",
                            'severity': 'medium',
                            'fix': "Implement cache warming for this model",
                            'details': {
                                'hit_rate': performance['hit_rate'],
                            },
                        })
                    
                    if performance['error_rate'] > 0.05:
                        issues.append({
                            'type': 'high_error_rate',
                            'message': f"Model {model_label} has high cache error rate ({performance['error_rate']:.2%})",
                            'severity': 'high',
                            'fix': "Check cache implementation for errors",
                            'details': {
                                'error_rate': performance['error_rate'],
                                'errors': performance['errors'],
                                'operations': performance['operations'],
                            },
                        })
                
                # Add to results
                results['issues'][model_label] = issues
                
                # Output results
                if output_format == 'text':
                    if issues:
                        self.stdout.write(f"    Found {len(issues)} issues:")
                        for issue in issues:
                            self.stdout.write(f"      [{issue['severity']}] {issue['message']}")
                            self.stdout.write(f"        Fix: {issue['fix']}")
                    else:
                        self.stdout.write("    No issues found")
                
                # Fix issues if requested
                if fix_issues and issues:
                    self.stdout.write(f"  Fixing issues for {model_label}...")
                    fixes = []
                    
                    for issue in issues:
                        if issue['type'] == 'low_consistency':
                            self.stdout.write(f"    Fixing low consistency...")
                            
                            # Reconcile cache
                            reconcile_stats = reconcile_cache_for_model(model, force=True, batch_size=100, max_instances=1000)
                            
                            fixes.append({
                                'type': 'reconcile',
                                'issue': issue['type'],
                                'success': True,
                                'details': reconcile_stats,
                            })
                            
                            self.stdout.write(f"      Reconciled {reconcile_stats['cached_instances']} instances")
                    
                    # Add to results
                    results['fixes'][model_label] = fixes
        
        # Output final results
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2))
        else:
            self.stdout.write(self.style.SUCCESS("Cache diagnostics completed"))
            
            # Summary
            self.stdout.write("\nSummary:")
            self.stdout.write(f"  Models checked: {results['models_checked']}")
            
            if check_consistency:
                consistency_issues = sum(1 for issues in results['issues'].values() for issue in issues if issue['type'] == 'low_consistency')
                self.stdout.write(f"  Models with consistency issues: {consistency_issues}")
            
            if check_performance:
                hit_rate_issues = sum(1 for issues in results['issues'].values() for issue in issues if issue['type'] == 'low_hit_rate')
                error_rate_issues = sum(1 for issues in results['issues'].values() for issue in issues if issue['type'] == 'high_error_rate')
                self.stdout.write(f"  Models with hit rate issues: {hit_rate_issues}")
                self.stdout.write(f"  Models with error rate issues: {error_rate_issues}")
            
            if check_issues:
                missing_timestamp_issues = sum(1 for issues in results['issues'].values() for issue in issues if issue['type'] == 'missing_timestamp')
                missing_version_issues = sum(1 for issues in results['issues'].values() for issue in issues if issue['type'] == 'missing_version')
                self.stdout.write(f"  Models missing timestamp field: {missing_timestamp_issues}")
                self.stdout.write(f"  Models missing version field: {missing_version_issues}")
            
            if fix_issues:
                fixes = sum(len(fixes) for fixes in results['fixes'].values())
                self.stdout.write(f"  Issues fixed: {fixes}")
            
            # Recommendations
            self.stdout.write("\nRecommendations:")
            if any(issues for issues in results['issues'].values()):
                for model_label, issues in results['issues'].items():
                    if issues:
                        self.stdout.write(f"  {model_label}:")
                        for issue in issues:
                            self.stdout.write(f"    - {issue['fix']}")
            else:
                self.stdout.write("  No issues found")
            
            # Next steps
            self.stdout.write("\nNext steps:")
            self.stdout.write("  1. Address any missing timestamp or version fields")
            self.stdout.write("  2. Run 'python manage.py reconcile_cache' to fix consistency issues")
            self.stdout.write("  3. Implement cache warming for models with low hit rates")
            self.stdout.write("  4. Check cache implementation for models with high error rates")
