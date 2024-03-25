function cmpf(const_id){
    let all_vars = $('input[id^="const_' + const_id + '"]')
    let list_params = []
    all_vars.each(function(){
        let dict_param = {}
        let re = new RegExp('const_' + const_id + '_user_data_(\\d+)')
        dict_param.id = this.id.match(re)[1]
        if (this.type === 'checkbox')
            dict_param.value = (this.checked) ? 'True' : 'False'
        else
            dict_param.value = this.value
        list_params.push(dict_param)
    })
    $.ajax({url:'calc-main-page-formula',
            method:'get',
            dataType:'json',
            data: {list_params: JSON.stringify(list_params), const_id: const_id},
            success:function(data){
                $('#div_const_' + const_id + '_result').html(data)
            },
            error: function () {
                $('#div_const_' + const_id + '_result').html('')
            }
        })
}