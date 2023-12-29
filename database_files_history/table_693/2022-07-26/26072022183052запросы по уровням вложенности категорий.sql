пример запроса товаров, лежащих в категории первого уровня вложенности
SELECT * FROM items where category_id in (
	select id from categories WHERE parent_id is NULL
)

товары, лежащие на втором уровне вложенности
SELECT * FROM items where category_id in (
	select id from categories WHERE parent_id in (
    	select id from categories where parent_id is NULL
    )
)

товары третьего уровня глубины
SELECT * FROM items where category_id in (
	select id from categories WHERE parent_id in (
    	select id from categories where parent_id in (
        	select id from categories where parent_id is NULL
        )
    )
)

четвертый уровень вложенности
SELECT * FROM items where category_id in (
	select id from categories WHERE parent_id in (
    	select id from categories where parent_id in (
        	select id from categories where parent_id in (
            	select id FROM categories WHERE parent_id is NULL
            )
        )
    )
)
