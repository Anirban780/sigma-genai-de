
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  SELECT 1 AS deliberate_bad_data_row
  
  
      
    ) dbt_internal_test